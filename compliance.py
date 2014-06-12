import simplejson
import requests
import config as cnfg
import problem_checker
import os
import copy

def check_compliance(is_id, search, email=None, password=None, server=None):
   global config
   user_config = str(os.path.dirname(os.path.abspath(__file__))) + "/user_config.txt"
   auto_config = str(os.path.dirname(os.path.abspath(__file__))) + "/auto_config.txt"
   config = cnfg.Config(user_config, auto_config)
   
   if email: config.user_email = email
   if password: config.user_pass = password
   if server: config.server = server
   
   #For testing/debugging
   if config.test_from_log_file:
      bugs = read_bugs()
   else:
      bugs = get_bugs(is_id, search)
      log_bugs(bugs)

   p = problem_checker.ProblemChecker(config)
   info, passed, ignored = p.find_problems(bugs)
   
   print "Found %d bug%s with problems" % (len(info), "s" if len(info) != 1 else "")
   
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


def read_bugs():
   f = open(config.log_folder + "results.txt")
   results = "\n".join(f.readlines())
   results = simplejson.loads(results)
   return results


def log_bugs(bugs):
   if not config.write_logs: return
   print "Writing findbugs query results."
   f = open(config.log_folder + "results.txt", "w")
   f.write(simplejson.dumps(bugs, indent=2))
   f.flush()
   f.close()


def write_data(info, name):
   if not config.write_logs: return
   print "Writing %s results." % name
   file_dir = str(os.path.dirname(os.path.abspath(__file__))) + "/"
   f = open(file_dir + "logs/%s.txt" % name, "w")
   mod = [copy.copy(i) for i in info]
   for i in mod:
      i["data"] = "ommited_info"
      i["clones"] = ", ".join(i["clones"])
      i["parents"] = ", ".join(i["parents"])
   f.write(simplejson.dumps(mod, indent=2))
   f.flush()
   f.close()


if __name__ == "__main__":
   #search = "https://bugzilla.redhat.com/buglist.cgi?cmdtype=dorem&list_id=2495370&namedcmd=test2&remaction=run&sharer_id=367466"
   #search = "https://bugzilla.redhat.com/buglist.cgi?quicksearch=rhel%206&list_id=2498549"
   search = "1033136"
   check_compliance(True, search)
