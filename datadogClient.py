import datadog

class datadogClient():
	def __init__(self, apiKey=None, appKey=None):
		"""
		Initialize a toggleable Datadog Client

		:param apiKey: Datadog api key. Leave empty to create a dummy (disabled) Datadog client.
		:param appKey: Datadog app key. Leave empty to create a dummy (disabled) Datadog client.
		"""
		if apiKey is not None and appKey is not None:
			print(str(apiKey))
			print(str(appKey))
			datadog.initialize(api_key=apiKey, app_key=appKey)
			self.client = datadog.ThreadStats()
			self.client.start()
		else:
			self.client = None

	def increment(self, *args, **kwargs):
		"""
		Call self.client.increment(*args, **kwargs) if this client is not a dummy

		:param args:
		:param kwargs:
		:return:
		"""
		if self.client is not None:
			self.client.increment(*args, **kwargs)

	def gauge(self, *args, **kwargs):
		"""
		Call self.client.gauge(*args, **kwargs) if this client is not a dummy

		:param args:
		:param kwargs:
		:return:
		"""
		if self.client is not None:
			self.client.gauge(*args, **kwargs)