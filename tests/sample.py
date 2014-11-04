from datetime import datetime
try:
	from StringIO import StringIO
except:
	from io import StringIO
import pical
import glob
import os.path
import logging
logging.basicConfig()

def test_parse():
	for f in glob.glob("%s/*.ics" % os.path.dirname(__file__)):
		for c in pical.parse(open(f,"rb")):
			fp = StringIO("\r\n".join(list(c.serialize())))
			pical.parse(fp)

def test_range():
	cal = pical.parse(open("%s/google_calendar_ex1.ics" % os.path.dirname(__file__),"rb"))[0]
	q = cal.time_range(datetime(2015,4,1,tzinfo=pical.utc), datetime(2015,6,1,tzinfo=pical.utc), expand=True)
	assert len([c for c in q.children if c.name=="VEVENT"])==10
	q = cal.time_range(datetime(2015,4,1,tzinfo=pical.utc), datetime(2015,6,1,tzinfo=pical.utc))
	assert len([c for c in q.children if c.name=="VEVENT"])==3

if __name__=="__main__":
	test_parse()
	test_range()
