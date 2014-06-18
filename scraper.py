from bs4 import BeautifulSoup
import simplejson
import requests
import re, os
import datetime
import sys


url = "https://pp.engineering.redhat.com/pp/data/rhel/"
server = "https://findbugs-seg.itos.redhat.com/"
tracker_form = "GSS_*_*_proposed"
phases = ("Planning", "Development", "Testing", "Launch", "Maintenance")
zphases = ("Development", "Kernel patch submission deadline", "QE", "Kernel GA Release")
last_relavent_version = 5


def main(email, password):
   global user_email, user_pass
   user_email, user_pass = email, password
   __get_highest_versions()
   __refine_version_info()
   __add_pendings()
   __get_tracker_ids()
   __update_config()
   print "Exit Success"


def __get_soup(url):
   return BeautifulSoup(requests.get(url, verify=False).text)


def __get_highest_versions():
   sys.stdout.write("Scraping broad version info...")
   global highest_versions
   highest_versions = {}
   soup = __get_soup(url)
   for link in soup.find_all('a', href=re.compile("rhel-")):
      parts = link['href'].split("-")
      major = int(parts[1].split(".")[0])
      minor = int(parts[2])
      #Ignore old useless versions
      if major < last_relavent_version:
         continue
      #If higher version found, replace
      if major not in highest_versions or highest_versions[major] < minor:
         highest_versions[major] = minor
   print "Done."


def __refine_version_info():
   sys.stdout.write("Scraping specific version info...")
   global got_info
   got_info = {"phases": {}, "zstream": {}}
   
   #Format specifiers
   version_matcher = re.compile(r'\s\d+.\d+')
   digits_matcher = re.compile(r'\d+')
   matcher = re.compile(r'^\d+.\d+$')
   date_format = "%a %Y-%m-%d"
   out_format = "%m-%d-%Y"
   current_time = datetime.datetime.now()
   
   #Check each relavent highest version
   for major, p_minor in highest_versions.iteritems():
      minor = p_minor
      current = True
      
      #Go down the list of minor versions for each major version until we hit old useless data
      #while current and minor >= 0:
      while minor >= 0:
         #These help watch for and handle weird boundary cases
         min_date = datetime.datetime.max
         max_date = datetime.datetime.min
         closest = datetime.datetime.min
         closest_phase = None
         
         this_ver = None   #Tracks the hierarchy number of the info we're actually looking for
         main_hier = None  #Trackers the hierarchy number of the maintenance phase
         kernel = None
         found = False     #Did a valid phase exist for a given sub version (not a bad webage)?
         inside = False    #Was the current date inside one of these phases?

         key = str(major) + "." + str(minor)

         #Get and scroll through soup data
         soup = __get_soup(url + "rhel-%d-%d-0/" % (major, minor))
         for row in soup.find_all("tr"):
            info = row.text.strip().split("\n")
            if len(info) < 4:
               continue

            #Info variables for simplicity
            hier_num = info[0].strip()
            phase_name = info[1].strip()

            #Find version mappings
            if '.' not in hier_num:
               matched_version = version_matcher.search(phase_name)
               if matched_version:
                  matched_version = matched_version.group(0).strip().split(".")
                  if (int(matched_version[0]), int(matched_version[1])) == (major, minor):
                     this_ver = hier_num
                     
            #Find main phases
            elif matcher.match(hier_num) and any(phase in phase_name for phase in phases):
               #Unmapped key (there is version info besides the version we're looking for)
               if hier_num.split(".")[0] != this_ver:
                  continue
               start = datetime.datetime.strptime(info[2], date_format)
               end = datetime.datetime.strptime(info[3], date_format)
               
               #Handle z-stream
               if "Maintenance" in phase_name:
                  main_hier = hier_num
                  found = True
                  continue
               
               #Valid non-maintenance phase was found for this version
               min_date = start if start < min_date else min_date
               max_date = end if end > max_date else max_date
               found = True
               
               if current_time >= start:
                  #Set closest flag
                  if start > closest:
                     closest = start
                     closest_phase = phase_name
                  
                  #Set phase info if valid
                  if current_time < end:
                     if not key in got_info["phases"]:
                        got_info["phases"][key] = []
                     got_info["phases"][key].append(str(phase_name))
                     inside = True
                     
            #Find phase of z-stream
            elif main_hier and hier_num.startswith(main_hier):
               #Dates of kernel / kernel phase
               start = datetime.datetime.strptime(info[2], date_format)
               end = datetime.datetime.strptime(info[3], date_format)
               start = start.strftime(out_format)
               end = end.strftime(out_format)
               
               #Find digit matches in name (e.g. [2, 15] from "Kernel 2 - Kernel 15")
               digs = [int(found) for found in digits_matcher.findall(phase_name)]
               
               #If name contains "kernel" and a kernel number
               if "kernel" in phase_name.lower() and digs:
                  #Set current kernel if only 1 digit found, but None if range found
                  kernel = str(digs[0]) if len(digs) == 1 else None
                  
                  #Make room for this version (e.g. 7.0)
                  if key not in got_info["zstream"]:
                     got_info["zstream"][key] = {}
   
                  #Set start and end dates for range of kernels, or just 1 kernel if there's only 1
                  for kvers in xrange(digs[0], digs[0] + 1 if kernel else digs[1] + 1):
                     kvers = str(kvers)
                     if kvers not in got_info["zstream"][key]:
                        got_info["zstream"][key][kvers] = {"data": {}, "start": start, "end": end}
               
               #If phase data exists for the kernel, store it
               if kernel and any(phase in phase_name for phase in zphases):               
                  got_info["zstream"][key][kernel]["data"][phase_name] = (start, end)
            
         #Check that versions are still relevant            
         if found and not inside:
            #Version has yet to enter life-cycle
            if min_date > current_time:
               if not key in got_info["phases"]:
                  got_info["phases"][key] = []
               got_info["phases"][key].append("Pending")  
                       
            #If seemingly irrelevant, check boundary case
            elif current_time > min_date and current_time < max_date:
               print "Version %s is not explicitly in any phase," % key
               print "but the current date still falls within its lifecycle."
               print "Assuming %d.%d to be in %s." % (major, minor, closest_phase)
            else:
               #Break out of loop because we're now checking old and irrelevant versions
               current = False 
         minor -= 1
   print "Done."


def __add_pendings():
   global got_info
   #Make a list of versions that still need pending releases
   pendings = {} #Map of major versions to [boolean of whether pending release exists, highest vers]
   for vers in got_info["phases"]:
      tup = vers.split(".")
      if not tup[0] in pendings:
         pendings[tup[0]] = [False, tup[1]]
      if tup[1] > pendings[tup[0]][1]:
         pendings[tup[0]][1] = tup[1]
      if "Pending" in got_info["phases"][vers]:
         pendings[tup[0]][0] = True
   
   #Add the next version up if it needs pending
   for vers, tup in pendings.iteritems():
      key = str(vers) + "." + str(int(tup[1]) + 1)
      if not tup[0]:
         if not key in got_info["phases"]:
            got_info["phases"][key] = []
         got_info["phases"][key].append("Pending")
         

def __get_tracker_ids():
   sys.stdout.write("Getting tracker info...")
   global got_info
   trackers = {}
   for version in got_info["phases"]:
      tup = version.split(".")
      track = tracker_form.replace("*", tup[0], 1)
      track = track.replace("*", tup[1], 1)
      values = {"username" : user_email, "password" : user_pass, "id" : track, "url" : "", "fields" : ""}
      result = requests.post(server, data=values, verify=False).text
      try:
         result = simplejson.loads(result)
         trackers[version] = result["bugs"][0]["id"]
         if len(result["bugs"]) > 1:
            print "More than one bug found for the alias %s- using first." % track
      except:
         pass
         #print "Tracker for %s does not exist. Skipping." % track
   got_info["trackers"] = trackers
   print "Done."


def __update_config():
   #Make sure data has been scraped before we try to write it
   global got_info
   sys.stdout.write("Writing config file...")
   path = str(os.path.dirname(os.path.abspath(__file__))) + "/"   
   f = open(path + "res/auto_config.json", "w")
   f.write(simplejson.dumps(got_info, indent=2))
   print "Done."


if __name__ == "__main__":
   args = sys.argv
   if len(args) >= 3:
      main(args[1], args[2])
   else:
      print "MISSING ARGS: correct usage - 'python scraper.py email password'"