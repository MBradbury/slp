
class memodict(dict):
	def __init__(self, func):
		self.func = func

	def __call__(self, *args):
		return self[args]

	def __missing__(self, key):
		self[key] = result = self.func(*key)
		return result

def memoize(func):
	return memodict(func)
