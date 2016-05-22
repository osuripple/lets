import MySQLdb
import datetime
from helpers import consoleHelper
from constants import bcolors

class db:
	"""
	A MySQL db connection
	"""

	def __init__(self, host, username, password, database):
		"""
		Create a connection to a MySQL database

		host -- hostname
		username -- MySQL username
		password -- MySQL password
		database -- MySQL database name
		"""
		self.connection = MySQLdb.connect(host, username, password, database)

	def execute(self, query, params = ()):
		"""
		Executes a query

		query -- Query to execute. You can bind parameters with %s
		params -- Parameters list. First element replaces first %s and so on. Optional.
		"""
		try:
			#st = datetime.datetime.now()
			cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
			cursor.execute(query, params)
			self.connection.commit()
		finally:
			if cursor:
				cursor.close()

			#et = datetime.datetime.now()
			#tt = float((et.microsecond-st.microsecond)/1000)
			#consoleHelper.printColored("Request time: {}ms".format(tt), bcolors.PINK)

	def fetch(self, query, params = (), all = False):
		"""
		Fetch a single value from db that matches given query

		query -- Query to execute. You can bind parameters with %s
		params -- Parameters list. First element replaces first %s and so on. Optional.
		all -- Fetch one or all values. Used internally. Use fetchAll if you want to fetch all values.
		"""
		try:
			#st = datetime.datetime.now()
			cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
			cursor.execute(query, params)
			if all == True:
				return cursor.fetchall()
			else:
				return cursor.fetchone()
		finally:
			if cursor:
				cursor.close()

			#et = datetime.datetime.now()
			#tt = float((et.microsecond-st.microsecond)/1000)
			#consoleHelper.printColored("Request time: {}ms".format(tt), bcolors.PINK)

	def fetchAll(self, query, params = ()):
		"""
		Fetch all values from db that matche given query.
		Calls self.fetch with all = True.

		query -- Query to execute. You can bind parameters with %s
		params -- Parameters list. First element replaces first %s and so on. Optional.
		"""
		return self.fetch(query, params, True)
