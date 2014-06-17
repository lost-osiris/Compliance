import simplejson, requests, os

class ExtraInfo:
   
   def __init__(self, config):
      self.c = config
      self.trackers = []
      self.have = {}
      self.need = {}
      self.__get_trackers
   
   
   def __get_trackers(self):
      for version in self.c.trackers:
         self.trackers.append(self.c.trackers[version])
   
   
   def add_have(self, bug):
      self.have[bug["id"]] = bug
      
   
   def add_need(self, bug_id):
      if not bug_id in self.trackers:
         self.need[bug_id] = True
   
   
   def get_info(self):
      self.__filter()
      
      if len(self.need) == 0: return 
      
      #Allows debugging from file
      if self.c.test_from_log_file:
         bugs = self.__read_bugs()
      else:
         bugs = self.__query()
         self.__log_bugs(bugs)

      #Dictionary assignment for easy referencing
      for bug in bugs["bugs"]:
         self.have[bug["id"]] = bug
      
      
   def __filter(self):
      for bug_id in self.have:
         if bug_id in self.need:
            self.need.pop(bug_id)

               
   def __query(self):
      values={"username" : self.c.user_email, "password" : self.c.user_pass,
              "id" : ", ".join(self.need),
              "url" : "",
              "fields" : "flags, external_bugs, comments"}
      results = requests.post(self.c.server, data=values, verify=False).text
      results = simplejson.loads(results)
      return results


   def __log_bugs(self, bugs):
      if not self.c.write_logs: return
      print "Writing findbugs query extra results."
      path = str(os.path.dirname(os.path.abspath(__file__))) + "/"   
      f = open(path + self.c.log_folder + "/extra_results.txt", "w")
      f.write(simplejson.dumps(bugs, indent=2))
      f.flush()
      f.close()
      
      
   def __read_bugs(self):
      f = open(self.c.log_folder + "extra_results.txt")
      results = "\n".join(f.readlines())
      results = simplejson.loads(results)
      return results      
   
   