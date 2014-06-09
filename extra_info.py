import simplejson, requests

class ExtraInfo:
   
   def __init__(self, bugs, config):
      self.bugs = bugs
      self.c = config
      self.have_bugs = {}
      self.need_bugs = {}
   
   
   def get_info(self):
      self.__compile_ids()
      self.__query()
      
      
   def __compile_ids(self):
      for bug in self.bugs["bugs"]:
         if bug["id"] in self.have_bugs:
            continue
         self.have_bugs[bug["id"]] = {"trackers": []}
         
      for bug in self.bugs["bugs"]:
         for bug_id in bug["blocks"]:
            if not bug_id in self.have_bugs and not bug_id in self.need_bugs:
               self.need_bugs[bug_id] = True
         for bug_id in bug["depends_on"]:
            if not bug_id in self.have_bugs and not bug_id in self.need_bugs:
               self.need_bugs[bug_id] = True
               
               
   def __query(self):
      values={"username" : self.c.user_email, "password" : self.c.user_pass,
              "id" : ", ".join(self.need_bugs),
              "url" : "",
              "fields" : "flags, external_bugs"}
      print ", ".join(self.need_bugs)
      results = requests.post(self.c.server, data=values, verify=False).text
      results = simplejson.loads(results)
      return results