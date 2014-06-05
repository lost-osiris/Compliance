'''
Reads config file and stores data.
'''
import os

class Config:

   def read_config(self, file_name, processor):
      config = open(file_name)
      line = config.readline()
      count = 1
      while len(line) > 0:
         line = line.strip()
         #Ignore comments and empty lines
         if len(line) == 0 or line[0] == "#":
            count += 1
            line = config.readline()
            continue;
         #Catch config file errors
         try:  
            field = line[0 : line.index("=")].strip()
            value = line[line.index("=") + 1:].strip()
            if not processor(field, value):
               print "Unrecognized field in config file %s (line %d ). Ignoring." % (file_name, count)
         except:
            print "Invalid config file (line " + str(count) + "). Exiting."
            exit()
         count += 1
         line = config.readline()
         
 
   def __process_user(self, field, value):
      if field == "username":
         self.user_email = value
         if not "@" in value:
            self.user_email += "@redhat.com"
      elif field == "password":
         self.user_pass = value
      elif field == "server":
         self.server = value
      elif field == "salesforce":
         self.valid_sales_force.append(value)
      elif field == "ignore":
         self.ignore.append(value)
      elif field == "ignore_closed_bugs":
         self.ignore_closed_bugs = True if value.lower() == "true" else False
      elif field == "require_sales_force":
         self.require_sales_force = True if value.lower() == "true" else False
      elif field == "test_from_log_file":
         self.test_from_log_file = True if value.lower() == "true" else False
      elif field == "log_folder":
         self.log_folder = str(os.path.dirname(os.path.abspath(__file__))) + "/" + value
      else:
         return False
      return True

      
   def __process_auto(self, field, value):
      major_minor = field.split(".")
      vers = (int(major_minor[0]), int(major_minor[1]))
      phase_tracker = value.split("|")
      phases = phase_tracker[0].split(", ")
      tracker = phase_tracker[1]
      #Add phases mappings
      for phase in phases:
         self.phases[vers] = phase
      #Add tracker mappings
      if len(tracker) > 0:
         self.trackers[vers] = tracker
      return True


   def __init__(self, user_config = "user_config.txt", auto_config = "auto_config.txt"):
      self.ignore_closed_bugs = True
      self.require_sales_force = True
      self.test_from_log_file = None
      self.user_email = None
      self.user_pass = None
      self.server = None
      self.log_folder = None
      self.trackers = {}
      self.phases = {}
      self.ignore = []
      self.valid_sales_force = []
      user_config = str(os.path.dirname(os.path.abspath(__file__))) + "/" + user_config
      auto_config = str(os.path.dirname(os.path.abspath(__file__))) + "/" + auto_config
      self.read_config(user_config, self.__process_user)
      self.read_config(auto_config, self.__process_auto)
