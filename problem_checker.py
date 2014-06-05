import inspect, re
import config as cnfg

class ProblemChecker:
   
   nvr_matcher = re.compile(r'rhel-(\d+).(\d+)')
   z_stream_matcher = re.compile(r'rhel-\d+.\d+.z')
   
   def __init__(self, config = None):
      self.current_sf = False
      self.current_nvr = None
      self.c = config
      self.checks = {}
      if not config:
         self.c = cnfg.Config()
      checks = [name_val for name_val in inspect.getmembers(self)\
                if inspect.ismethod(name_val[1]) and "_pcheck" in name_val[0]]
      for check in checks:
         self.checks[check[1]] = " ".join(check[0].split("_")[3 : -1]).title()


   ''' PROBLEM CHECKS GO HERE,   '''
   ''' AND MUST END WITH _pcheck '''
   ''' IN ORDER TO BE EXECUTED   '''
   
   def __no_relevant_sales_force_case_pcheck(self, bug):
      if not self.__req_sf():
         desc = ("This bug is not associated with any of the Sales Force cases "
            "that this compliance filter is set up to handle (%s). If this is "
            "by mistake, attach an appropriate SF case and reanalyze for the "
            "complete list of problems.") % ", ".join(self.c.valid_sales_force)
         self.__add_problem(bug, desc)
   
   
   def __missing_or_incorrect_tracker_pcheck(self, bug):
      pass
      
      
   def __nvr_flag_is_missing_pcheck(self, bug):
      if self.__req_sf() and len(self.current_nvr) == 0:
         desc = ("bug does not have an NVR (name-version-revision) flag set; "
                 "add a flag in the form 'rhel-#.#.#' to resolve.")
         self.__add_problem(bug, desc)


   def __nvr_flag_is_outdated_pcheck(self, bug):
      if self.__req_sf() and len(self.current_nvr) > 0:
         has_a_current_flag = False
         highest = self.current_nvr[0][0]
         for flag in self.current_nvr:
            if flag[0][0] > highest[0] or (flag[0][0] == highest[0] and flag[0][1] > highest[1]):
               highest = flag[0] 
            if flag[0] in self.c.phases:
               phase = self.c.phases[flag[0]]
               if flag[1] or "Planning Phase" in phase or "Pending" in phase:
                  has_a_current_flag = True
         if not has_a_current_flag:
            possible_flags = []
            #Find suggestions for update flag
            for vers, phase in self.c.phases.iteritems():
               if "Planning Phase" in phase or "Pending" in phase:
                  if vers[0] > highest[0] or (vers[0] == highest[0] and vers[1] > highest[1]):
                     possible_flags.append(vers)
            if possible_flags > 1:
               possible_flags = [flag for flag in possible_flags if flag in self.c.trackers]
            if len(self.current_nvr) > 1:
               desc = "none of the NVR flags (highest=%d.%d) for this bug " % (highest[0], highest[1])
            else:
               desc = "the NVR flag for this bug (%d.%d) does not " % (highest[0], highest[1])
            desc += "match any of the current appropriate versions of RHEL."
            if possible_flags > 0:
               possible_flags.sort()
               desc += " Please add an NVR flag with one of the following versions: %s" % ", ".join(["%d.%d" % (v[0], v[1]) for v in possible_flags])
            self.__add_problem(bug, desc)


   def __priority_tag_is_not_set_pcheck(self, bug):
      if self.__req_sf() and "unspecified" in bug['priority']:
         self.__add_problem(bug)
         
         
   def __severity_tag_is_not_set_pcheck(self, bug):
      if self.__req_sf() and "unspecified" in bug['severity']:
         self.__add_problem(bug)
         
   ''' END OF PROBLEM CHECKS'''


   def find_problems(self, bugs):
      #Clear old problem set
      self.problems = {}
      
      #Go through all the bugs
      for bug in bugs['bugs']:
         #Ignore closed bugs
         if self.c.ignore_closed_bugs and not bug['is_open'] == "True":
            continue
         
         #Set class variables for use across functions
         self.__has_sales_force_case(bug)
         self.__get_nvr(bug)
         
         #Apply all checks unless set to be ignored
         for check in self.checks:
            if not self.checks[check] in self.c.ignore:
               check(bug)
               
      #Report back results
      return self.problems


   def __has_sales_force_case(self, bug):
      for ext_bug in bug['external_bugs']:
         sf_desc = ext_bug['type']['description']
         if any(sf in sf_desc for sf in self.c.valid_sales_force):
            self.current_sf = True
            return
      self.current_sf = False
      
      
   def __req_sf(self):
      if not self.c.require_sales_force:
         return True
      return self.current_sf
   
   
   def __get_nvr(self, bug):
      self.current_nvr = []
      for flag in bug['flags']:
         match = ProblemChecker.nvr_matcher.search(flag["name"])
         zstream = False
         if match:
            if ProblemChecker.z_stream_matcher.search(flag["name"]):
               zstream = True
            self.current_nvr.append(((int(match.group(1)), int(match.group(2))), zstream))
            

   def __add_problem(self, bug, desc = ""):
      #Transform caller function into an ID
      problem_id = " ".join(inspect.stack()[1][3].split("_")[2 : -1]).title()
      bug_id = bug['id']
      if bug_id not in self.problems:
         self.problems[bug_id] = {"data" : bug, "problems" : []}
      self.problems[bug_id]["problems"].append({"id" : problem_id, "desc" : desc})

