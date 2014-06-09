import simplejson
import requests
import config as cnfg
import problem_checker
import os
import extra_info as ex_in

def check_compliance(is_id, get_extra_info, search, email=None, password=None, server=None):
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
   problems, warnings, passed = p.find_problems(bugs)
   write_problems(problems)
   
   print "Found %d bug%s with problems" % (len(problems), "s" if len(problems) != 1 else "")
   
   extra_info = None
   if get_extra_info:
      ei = ex_in.ExtraInfo(bugs, config)
      extra_info = ei.get_info()
   
   return problems, warnings, passed, extra_info
   

def get_bugs(is_id, search):
   values={"username" : config.user_email, "password" : config.user_pass,
           "id" : search if is_id else "",
           "url" : "" if is_id else search,
           "fields" : "flags, external_bugs"}
   results = requests.post(config.server, data=values, verify=False).text
   results = simplejson.loads(results)
   return results


def read_bugs():
   f = open(config.log_folder + "results.txt")
   results = "\n".join(f.readlines())
   results = simplejson.loads(results)
   return results


def log_bugs(bugs):
   f = open(config.log_folder + "results.txt", "w")
   f.write(simplejson.dumps(bugs, indent=2))
   f.flush()
   f.close()


def write_problems(problems):
   file_dir = str(os.path.dirname(os.path.abspath(__file__))) + "/"
   f = open(file_dir + "logs/compliance.txt", "w")
      
   #Loop through bugs
   for bug in problems:
      f.write("Bug %s\n" % bug)
      for problem in problems[bug]["problems"]:
         f.write("  -%s" % problem["id"])
         if len(problem["desc"]) > 0:
            f.write(": %s" % problem["desc"])
         f.write("\n")
      f.write("\n")
      
   f.flush()
   f.close()


if __name__ == "__main__":
   search = "https://bugzilla.redhat.com/buglist.cgi?cmdtype=dorem&list_id=2495370&namedcmd=test2&remaction=run&sharer_id=367466"
   #search = "https://bugzilla.redhat.com/buglist.cgi?quicksearch=rhel%206&list_id=2498549"
   check_compliance(False, True, search)
