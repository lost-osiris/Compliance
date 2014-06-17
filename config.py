import os
import simplejson

class Config:

   def read_config(self, file_name):
      f = open(file_name)
      data = simplejson.loads("\n".join(f.readlines()))
      f.close()
      #Assign dot-accessible values to class
      for key, value in data.iteritems():
         self.__dict__[key] = value
      

   def __init__(self, folder = None):
      #Find file path
      path = os.path.dirname(os.path.abspath(__file__)) + "/"
      if folder: path += folder + "/"
      path.replace("//", "/")
      
      #Initialize values to defaults
      self.read_config(path + "defaults.json"
                       )
      #Reassign to custom settings if applicable
      self.read_config(path + "user_config.json")
      self.read_config(path + "auto_config.json")
