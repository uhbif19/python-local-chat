import json, pathlib

# %TODO: check types

class DictDB(dict):

	filename = None # File name of JSON file, where DB is stored
	save_always = True

	def __init__(self, filename, save_always=True):
		self.filename = filename
		self._path = pathlib.Path(filename)
		self.save_always = save_always
		super(self.__class__).__init__()

		self.reload()

	def reload(self):
		if not self._path.exists():
			self._path.open("w").write("{}")
		self.update(json.load(self._path.open("r")))

	def save(self):
		json.dump(self, self._path.open("w"))

	def __setitem__(self, key, value):
		super(self.__class__, self).__setitem__(key, value)
		if self.save_always:
			self.save()

	def __delitem__(self, key):
		super(self.__class__, self).__delitem__(key)
		if self.save_always:
			self.save()