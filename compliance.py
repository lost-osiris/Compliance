import simplejson
import requests
import config as cnfg
import problem_checker
import os
import copy

def check_compliance(is_id, search, email=None, password=None, server=None, results=None):
   global config
   config = cnfg.Config("res")
   
   #Convert string NVRs to tuple of major and minor versions e.g.: 7.0 -> (7, 0)
   config.phases = dict((tuple(int(i) for i in key.split(".")), value) for (key, value) in config.phases.iteritems())
   config.trackers = dict((tuple(int(i) for i in key.split(".")), value) for (key, value) in config.trackers.iteritems())
   config.zstream = dict((tuple(int(i) for i in key.split(".")), value) for (key, value) in config.zstream.iteritems())
   
   if email: config.user_email = email
   if password: config.user_pass = password
   if server: config.server = server
   
   #For testing/debugging
   if results != "" and is_id == False:
      bugs = results
   elif config.test_from_log_file:
      bugs = read_bugs()
   else:
      bugs = get_bugs(is_id, search)
      log_bugs(bugs)

   p = problem_checker.ProblemChecker(config)
   info, passed, ignored = p.find_problems(bugs)
   
   info = modify(info)
   passed = modify(passed)
   ignored = modify(ignored)
   
   write_data(info, "compliance")
   write_data(passed, "passed")
   write_data(ignored, "ignored")
   
   return info, passed, ignored
   

def get_bugs(is_id, search):
   values={"username" : config.user_email, "password" : config.user_pass,
           "id" : search if is_id else "",
           "url" : "" if is_id else search,
           "fields" : "flags, external_bugs, comments"}
   
   results = requests.post(config.server, data=values, verify=False).text
   results = simplejson.loads(results)
   return results


def modify(bugs):
   for bug in bugs:
      markers = {"CLOSED_ERRATA": False,
                 "HOTFIX_REQUESTED": False,
                 "HOTFIX_DELIVERED": False,
                 }
      
      #Mark this bug
      mark(bug["data"], markers)
      
      #Mark parents and clones
      for raw in bug["parents"].itervalues(): mark(raw, markers)
      for raw in bug["clones"].itervalues(): mark(raw, markers)
         
      #Set markers
      bug["markers"] = markers
      
   return bugs


def mark(raw_data, markers):
   closed_errata(raw_data, markers)
   hotfix(raw_data, markers)


def closed_errata(raw_data, markers):
   if not "closed" in raw_data["status"].lower():
      return
   if not "errata" in raw_data["resolution"].lower():
      return
   for comment in raw_data["comments"]:
      if comment["author"] == "errata-xmlrpc@redhat.com" and comment["is_private"] == "False":
         if "resolution of ERRATA" in comment["text"]:
            text = comment["text"]
            link = text.split("bug report.\n\n")[1]
            sf_count = count_sf(raw_data)
            raw_data["errata_link"] = link
            raw_data["errata_text"] = text
            raw_data["errata_sf"] = sf_count
            
            #Update markers
            if not markers["CLOSED_ERRATA"]:
               markers["CLOSED_ERRATA"] = []
            markers["CLOSED_ERRATA"].append({"link": link, 
                                             "text": text,
                                             "id": raw_data["id"],
                                             "sf_count": sf_count
                                             })
            return


def count_sf(raw_data):
   count = raw_data['external_bugs'].count(lambda x: x['type']['type'] == "SFDC")
   return count if count > 0 else "No SF case set"


def hotfix(raw_data, markers):
   for flag in raw_data["flags"]:
      if "hot_fix_requested" in flag["name"].lower():
         if "+" in flag["status"]:
            markers["HOTFIX_DELIVERED"] = True
            raw_data["hotfix_delivered"] = True
         else:
            markers["HOTFIX_REQUESTED"] = True
            raw_data["hotfix_requested"] = True
         return
   

def read_bugs():
   f = open(config.log_folder + "/results.txt")
   results = "\n".join(f.readlines())
   results = simplejson.loads(results)
   return results


def log_bugs(bugs):
   if not config.write_logs: return
   print "Writing findbugs query results."
   path = str(os.path.dirname(os.path.abspath(__file__))) + "/"   
   f = open(path + config.log_folder + "/results.txt", "w")
   f.write(simplejson.dumps(bugs, indent=2))
   f.flush()
   f.close()


def write_data(info, name):
   if not config.write_logs: return
   
   #Remove extra data from printed results (it's prettier)
   mod = [copy.copy(i) for i in info]
   
   if not config.write_extra:
      for i in mod:
         i["data"] = "ommited_info"
         i["clones"] = ", ".join(i["clones"])
         i["parents"] = ", ".join(i["parents"])
   
   #Open correct file path
   print "Writing %s results. (%d)" % (name, len(info))
   path = str(os.path.dirname(os.path.abspath(__file__))) + "/"   
   f = open(path + config.log_folder + "/%s.txt" % name, "w")
   
   #Write and close
   f.write(simplejson.dumps(mod, indent=2))
   f.flush()
   f.close()


if __name__ == "__main__":
   #search = "https://bugzilla.redhat.com/buglist.cgi?cmdtype=dorem&list_id=2495370&namedcmd=test2&remaction=run&sharer_id=367466"
   #search = "https://bugzilla.redhat.com/buglist.cgi?quicksearch=rhel%206&list_id=2498549"
   search = "1033136, 650113"
   check_compliance(True, search)
