import simplejson
import requests
import config as cnfg
import problem_checker
import os

def check_compliance(is_id, search, email=None, password=None, server=None):
   global config
   config = cnfg.Config()
   if not email: email = config.user_email
   if not password: password = config.user_pass
   if not server: server = config.server
   if config.test_from_log_file:
      bugs = read_bugs()
   else:
      bugs = get_bugs(is_id, search, email, password, server)
      log_bugs(bugs)
   p = problem_checker.ProblemChecker(config)
   problems = p.find_problems(bugs)
   write_problems(problems)
   print "Found %d bug%s with problems" % (len(problems), "s" if len(problems) != 1 else "")
   return problems
   

def get_bugs(is_id, search, email, password, server):
   values={"username" : email, "password" : password,
           "id" : search if is_id else "",
           "url" : "" if is_id else search,
           "fields" : "flags, external_bugs"}
   results = requests.post(server, data=values, verify=False).text
   results = simplejson.loads(results)
   return results


def read_bugs():
   f = open(config.log_folder + "results.txt")
   results = f.readline()
   results = simplejson.loads(results)
   return results


def log_bugs(bugs):
   f = open(config.log_folder + "results.txt", "w")
   f.write(simplejson.dumps(bugs))
   f.flush()
   f.close()


def write_problems(problems):
   file_dir = str(os.path.dirname(os.path.abspath(__file__))) + "/"
   f = open(file_dir + "logs/compliance.txt", "w")

   #Test code handling what to do with missing SF cases
   missing_sf = []
   ignore = []
   desc = None
   for bug in problems:
      for problem in problems[bug]["problems"]:
         if problem["id"] == "No Relevant Sales Force Case":
            if not desc: desc = problem["desc"]
            missing_sf.append(bug)
            if len(problems[bug]["problems"]) == 1:
               ignore.append(bug)
            continue
   for i in ignore:
      problems.pop(i, None)
      
   #Loop through bugs
   for bug in problems:
      f.write("Bug %s\n" % bug)
      for problem in problems[bug]["problems"]:
         if problem["id"] == "No Relevant Sales Force Case":
            missing_sf.append(bug)
            continue
         f.write("  -%s" % problem["id"])
         if len(problem["desc"]) > 0:
            f.write(": %s" % problem["desc"])
         f.write("\n")
      f.write("\n")
      
   #just for testing the SF thing
   if len(missing_sf) > 0:
      f.write("No Relevant Sales Force Case: %s\n" % desc)
      for bug in missing_sf: f.write("  -%s\n" % bug)
      
   f.flush()
   f.close()


'''
if __name__ == "__main__":
   search = "https://bugzilla.redhat.com/buglist.cgi?cmdtype=dorem&list_id=2495370&namedcmd=test2&remaction=run&sharer_id=367466"
   #search = "https://bugzilla.redhat.com/buglist.cgi?quicksearch=rhel%206&list_id=2498549"
   check_compliance(False, search)
'''
