from bs4 import BeautifulSoup
import simplejson
import requests
import re
import datetime
import sys


url = "https://pp.engineering.redhat.com/pp/data/rhel/"
server = "https://findbugs-seg.itos.redhat.com/"
tracker_form = "GSS_*_*_proposed"
phases = {"Planning", "Development", "Testing", "Launch"}
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
   global version_data
   version_data = {}
   
   #Format specifiers
   version_matcher = re.compile(r'\s\d+.\d+')
   matcher = re.compile(r'^\d+.\d+$')
   date_format = "%a %Y-%m-%d"
   current_time = datetime.datetime.now()
   
   #Check each relavent highest version
   for major, p_minor in highest_versions.iteritems():
      minor = p_minor
      current = True
      
      #Go down the list of minor versions for each major version until we hit old useless data
      while current and minor >= 0:
         #These help watch for and handle weird boundary cases
         min_date = datetime.datetime.max
         max_date = datetime.datetime.min
         closest = datetime.datetime.min
         closest_phase = None
         
         this_ver = None   #Tracks the hierarchy number of the info we're actually looking for
         found = False     #Did a valid phase exist for a given sub version (not a bad webage)?
         inside = False    #Was the current date inside one of these phases?

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
               found = True   #Valid phase was found for this version
               min_date = start if start < min_date else min_date
               max_date = end if end > max_date else max_date
               
               if current_time >= start:
                  #Set closest flag
                  if start > closest:
                     closest = start
                     closest_phase = phase_name
                     
                  #Set phase info if valid
                  if current_time < end:
                     key = (major, minor)
                     if not key in version_data:
                        version_data[key] = []
                     version_data[key].append(str(phase_name))
                     inside = True
                     
         #Check that versions are still relevant
         if found and not inside:
            #Version has yet to enter life-cycle
            if min_date > current_time:
               if not (major, minor) in version_data:
                  version_data[(major, minor)] = []
               version_data[(major, minor)].append("Pending")  
                       
            #If seemingly irrelevant, check boundary case
            elif current_time > min_date and current_time < max_date:
               print "Version %d.%d is not explicitly in any phase," % (major, minor)
               print "but the current date still falls within its lifecycle."
               print "Assuming %d.%d to be in %s." % (major, minor, closest_phase)
            else:
               #Break out of loop because we're now checking old and irrelevant versions
               current = False 
         minor -= 1
   print "Done."


def __add_pendings():
   global version_data
   #Make a list of versions that still need pending releases
   pendings = {} #Map of major versions to [boolean of whether pending release exists, highest vers]
   for vers in version_data:
      if not vers[0] in pendings:
         pendings[vers[0]] = [False, vers[1]]
      if vers[1] > pendings[vers[0]][1]:
         pendings[vers[0]][1] = vers[1]
      if "Pending" in version_data[vers]:
         pendings[vers[0]][0] = True
   
   #Add the next version up if it needs pending
   for vers, tup in pendings.iteritems():
      if not tup[0]:
         if not (vers, tup[1] + 1) in version_data:
            version_data[(vers, tup[1] + 1)] = []
         version_data[(vers, tup[1] + 1)].append("Pending")
         

def __get_tracker_ids():
   sys.stdout.write("Getting tracker info...")
   global trackers
   trackers = {}
   for version in version_data:
      track = tracker_form.replace("*", str(version[0]), 1)
      track = track.replace("*", str(version[1]), 1)
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
   print "Done."
   return trackers


def __update_config():
   #Make sure data has been scraped before we try to write it
   assert version_data and trackers
   sys.stdout.write("Writing config file...")
   f = open("../res/auto_config.txt", "w")
   keys = version_data.keys()
   keys.sort()
   for version in keys:
      f.write("%d.%d=%s|%s\n" % (version[0], version[1], ", ".join(version_data[version]),\
                                 trackers[version] if version in trackers else ""))
   f.flush()
   f.close()
   print "Done."


if __name__ == "__main__":
   args = sys.argv
   if len(args) >= 3:
      main(args[1], args[2])
   else:
      print "MISSING ARGS: correct usage - 'python scraper.py email password'"