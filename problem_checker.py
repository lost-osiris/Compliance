import inspect, re
import extra_info as ei
import config as cnfg

class ProblemChecker:

   nvr_matcher = re.compile(r'rhel-(\d+).(\d+)')
   z_stream_matcher = re.compile(r'rhel-\d+.\d+.z')

   severities = {"urgent": 0, "high": 1, "medium": 2, "low": 3, "unspecified": 4}

   def __init__(self, config = None):
      self.current_sf = False
      self.current_nvr = None
      self.current_zstream = False
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

   def __z_stream_clone_is_missing_acks_pcheck(self, bug):
      if not self.current_sf or not self.current_zstream or "zstream" in [word.lower() for word in bug["keywords"]]: return
      pmack = False
      develack = False
      qaack = False
      
      for flag in bug["flags"]:
         if flag["status"] == "+":
            if flag["name"] == "pm_ack":
               pmack = True
            elif flag["name"] == "devel_ack":
               develack = True
            elif flag["name"] == "qa_ack":
               qaack = True               
      
      if not pmack or not develack or not qaack:
         desc = ("zstream clones need to go through the same 3-ACK process that y-stream"
                 "bugs go through. No action is needed here from Support Delivery; PM EUS"
                 "will seek out these missing ACKS: %s%s%s") % ("" if pmack else " pm_ack",
                                                                "" if develack else " devel_ack",
                                                                "" if qaack else " qa_ack")
         self.__add_warning(bug, desc)


   def __not_yet_cloned_for_zstream_and_not_flagged_for_current_version_pcheck(self, bug):
      if not self.current_sf or not self.current_zstream or "zstream" in [word.lower() for word in bug["keywords"]]: return
      for flag in self.current_nvr:
         if flag[1]: continue #Looking for non-zstream flags
         if flag[0] in self.c.phases and self.c.phases[flag[0]] in ("Planning", "Pending", "Development", "Testing"):
            #Check flag status
            if flag[2] == "+": return
            desc = ("this bug is flagged for zstream, but its NVR flag ("
                    "%d.%d) does not have an ACK (+ status on flag)") % (flag[0][0], flag[0][1])
            self.__add_problem(bug, desc)
            return
      desc = ("this bug is flagged for zstream, but does not have an NVR ACK. This BZ"
              "needs to be fully ACK'd for the next Y release and its status must be"
              "'MODIFIED' before it can be cloned for zstream. Work with the SBR POC"
              "for accelerated fixes to resolve this")
      self.__add_problem(bug, desc)        
         
   
   def __no_relevant_sales_force_case_pcheck(self, bug):
      if self.__req_sf(): return
      desc = ("this bug is not associated with any of the Sales Force cases "
         "that this compliance filter is set up to handle (%s). If this is "
         "by mistake, attach an appropriate SF case and reanalyze for the "
         "complete list of problems.") % ", ".join(self.c.valid_sales_force)
      self.__add_warning(bug, desc)
   
   
   def __on_z_stream_without_gss_approved_pcheck(self, bug):
      if not self.__req_sf() or not self.current_zstream: return
      if "GSSApproved" in bug["cf_internal_whiteboard"] or "PMApproved" in bug["cf_internal_whiteboard"]: return
      zflags = [flag[0] for flag in self.current_nvr if flag[1]]
      desc = ("this bug is flagged for zstream (%s) but it does not "
              "contain the text 'GSSApproved' on its internal whiteboard. "
              "Please work with the SBR POC for accelerated fixes  to make "
              "this bug compliant.") % ", ".join(["%d.%d.z" % (f[0], f[1]) for f in zflags])
      self.__add_problem(bug, desc)
      
      
   def __gss_approved_without_z_stream_flag_pcheck(self, bug):
      if not self.__req_sf() or  self.current_zstream: return
      if not "GSSApproved" in bug["cf_internal_whiteboard"] or "ZStream" in bug["keywords"]: return
      desc = ("this bug contains the text 'GSSApproved' on its internal whiteboard. "
              "However, it has no z-stream NVR flag set. Please either set the z-stream "
              "flag for the appropriate version or remove the GSSApproved tag from the "
              "internal whiteboard.")
      self.__add_problem(bug, desc)      
         

   def __on_gss_tracker_without_corresponding_nvr_flag_set_pcheck(self, bug):
      if not self.__req_sf(): return
      for vers, tracker in self.c.trackers.iteritems():
         if tracker in bug["blocks"] and not any(vers == flag[0] for flag in self.current_nvr):
            desc = ("this bug is on the %d.%d GSS tracker (id=%s), but the %d.%d NVR flag is "
                    "not set. Please either set the flag or remove this bug from the tracker")\
                    % (vers[0], vers[1], tracker, vers[0], vers[1])
            self.__add_problem(bug, desc)
            
            
   def __flag_set_without_corresponding_tracker_pcheck(self, bug):
      if not self.__req_sf(): return
      for vers in self.current_nvr:
         if vers[1]: continue
         vers = vers[0]
         if vers in self.c.trackers and not self.c.trackers[vers] in bug["blocks"]:
            desc = ("this bug has the %d.%d NVR flag set, but is not on the %d.%d GSS tracker (id=%s). "
                    " Please either add the tracker or remove the flag from this bug")\
                    % (vers[0], vers[1], vers[0], vers[1], self.c.trackers[vers])
            self.__add_problem(bug, desc)      
      
      
   def __nvr_flag_is_missing_pcheck(self, bug):
      if not self.__req_sf() or len(self.current_nvr) > 0: return
      desc = ("this bug does not have any NVR flag set; "
              "add a flag in the form 'rhel-x.y.0' to resolve.")
      self.__add_problem(bug, desc)


   def __nvr_flag_is_outdated_pcheck(self, bug):
      #If has SF and at least 1 NVR flag
      if not self.__req_sf() or self.current_zstream or len(self.current_nvr) == 0: return
      has_a_current_flag = False
      highest = self.current_nvr[0][0] #Keep track of highest NVR flag
      for flag in self.current_nvr:
         if flag[2] == "+": return #Okay if has ACK
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
         desc = ("the priority tag for this bug is unspecified. "
                 "Please set it to match the associated SF case.")
         self.__add_problem(bug, desc)
         
         
   def __severity_tag_is_not_set_pcheck(self, bug):
      if self.__req_sf() and "unspecified" in bug['severity']:
         desc = ("the severity tag for this bug is unspecified. "
                 "Please set it to match the associated SF case.")
         self.__add_problem(bug, desc)
         
   ''' END OF PROBLEM CHECKS'''


   def find_problems(self, bugs):
      #Clear old problem set
      self.info = {}
      self.passed = []
      self.ignored = []
      
      extra_info = ei.ExtraInfo(self.c)
      
      #Go through all the bugs
      for bug in bugs["bugs"]:
         extra_info.add_have(bug)
         
         #Set class variables for use across functions
         self.__has_sales_force_case(bug)
         self.__get_nvr(bug)
         
         #Extra info if in zstream
         if self.current_zstream or "ZStream" in bug["keywords"]:
            for bug_id in bug["depends_on"]:
               extra_info.add_need(bug_id)
            for bug_id in bug["blocks"]:
               extra_info.add_need(bug_id)

         #Ignore closed bugs
         if self.c.ignore_closed_bugs and not bug["is_open"] == "True":
            self.__add_no_problem(bug, self.ignored)
            continue
         
         #Apply all checks unless set to be ignored
         for check in self.checks:
            if not self.checks[check] in self.c.ignore:
               check(bug)

         #No problems were added. It passed.
         if not bug["id"] in self.info:
            self.__add_no_problem(bug, self.passed)
      
      self.info = [self.info[bug] for bug in self.info]
      #Sort by: does it have problems, severity, priority, id
      self.info.sort(key = lambda bug: (0 if len(bug["problems"]) > 0 else 1,
                                         self.severities[bug["data"]["severity"]],
                                         self.severities[bug["data"]["priority"]],
                                         bug["id"]))
      #Just sort by id
      self.passed.sort(key = lambda bug: bug["id"])
      self.ignored.sort(key = lambda bug: bug["id"])
      
      #Get extra information (parents and clones)
      extra_info.get_info()
      
      #Associate extra info with correct bugs
      self.__associate_info(extra_info, self.passed)
      self.__associate_info(extra_info, self.ignored)
      self.__associate_info(extra_info, self.info)
      
      #Report back results
      return self.info, self.passed, self.ignored


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
      self.current_zstream = False
      for flag in bug['flags']:
         match = ProblemChecker.nvr_matcher.search(flag["name"])
         zstream = False
         if match:
            if ProblemChecker.z_stream_matcher.search(flag["name"]):
               self.current_zstream = True
               zstream = True
            # Example: ((7, 1), False, +)
            self.current_nvr.append(((int(match.group(1)), int(match.group(2))), zstream, flag["status"]))
            

   def __add_problem(self, bug, desc = ""):
      #Transform caller function into an ID
      problem_id = " ".join(inspect.stack()[1][3].split("_")[2 : -1]).title()
      bug_id = bug['id']
      if bug_id not in self.info:
         self.info[bug_id] = {"id": bug_id, "problems": [], "warnings": [], "data": bug,
                                  "parents": {}, "clones": {}, "status": 0}
      self.info[bug_id]["problems"].append({"id" : problem_id, "desc" : desc})
      
      
   def __add_warning(self, bug, desc = ""):
      #Transform caller function into an ID
      warning_id = " ".join(inspect.stack()[1][3].split("_")[2 : -1]).title()
      bug_id = bug['id']
      if bug_id not in self.info:
         self.info[bug_id] = {"id": bug_id, "problems": [], "warnings": [], "data": bug,
                                  "parents": {}, "clones": {}, "status": 0}
      self.info[bug_id]["warnings"].append({"id" : warning_id, "desc" : desc})
      
      
   def __add_no_problem(self, bug, to_list):
      to_list.append({"id": bug["id"], "data": bug, "parents": {}, "clones": {}})
   
   
   def __associate_info(self, extra_info, to_list):
      for bug in to_list:
         data = bug["data"]
         for bug_id in data["depends_on"]:
            get_bug = extra_info.have[bug_id] if bug_id in extra_info.have else None
            if get_bug and (data["summary"] in get_bug["summary"] or get_bug["summary"] in data["summary"]):
               bug["parents"][bug_id] = get_bug
         for bug_id in data["blocks"]:
            get_bug = extra_info.have[bug_id] if bug_id in extra_info.have else None
            if get_bug and (data["summary"] in get_bug["summary"] or get_bug["summary"] in data["summary"]):
               bug["clones"][bug_id] = get_bug
      
