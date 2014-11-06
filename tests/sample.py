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

def test_caldav_7_8_1():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		print("**** %s ****" % f)
		for c in pical.parse(open(f,"rb")):
			# <C:time-range start="20060104T000000Z" end="20060105T000000Z"/>
			u = c.time_range(time_range=[datetime(2006,1,4,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)])
			if u.name != "VCALENDAR":
				continue
			if len([c for c in u.children if c.name=="VEVENT"]):
				for l in u.serialize():
					print(l)

def test_caldav_7_8_2():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		print("**** %s ****" % f)
		for c in pical.parse(open(f,"rb")):
			# <C:limit-recurrence-set start="20060103T000000Z" end="20060105T000000Z"/>
			u = c.time_range(recur=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)])
			if u.name != "VCALENDAR":
				continue
			if len([c for c in u.children if c.name=="VEVENT"]):
				for l in u.serialize():
					print(l)

def test_caldav_7_8_3():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		print("**** %s ****" % f)
		for c in pical.parse(open(f,"rb")):
			# <C:expand start="20060103T000000Z" end="20060105T000000Z"/>
			u = c.time_range(expand=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)])
			if u.name != "VCALENDAR":
				continue
			if len([c for c in u.children if c.name=="VEVENT"]):
				for l in u.clone(in_utc=True).serialize():
					print(l)

def test_caldav_7_8_4():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		print("**** %s ****" % f)
		for c in pical.parse(open(f,"rb")):
			# <C:limit-freebusy-set start="20060102T000000Z" end="20060103T000000Z"/>
			u = c.time_range(time_range=[datetime(2006,1,2,tzinfo=pical.utc), datetime(2006,1,3,tzinfo=pical.utc)])
			if u.name != "VCALENDAR":
				continue
			if len([c for c in u.children if c.name=="VFREEBUSY"]):
				for l in u.time_filter(fb_range=[datetime(2006,1,2,tzinfo=pical.utc), datetime(2006,1,3,tzinfo=pical.utc)]).serialize():
					print(l)

def test_caldav_7_8_5():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		print("**** %s ****" % f)
		for c in pical.parse(open(f,"rb")):
			# <C:time-range start="20060106T100000Z" end="20060107T100000Z"/>
			u = c.time_range(alarm_range=[datetime(2006,1,6,10,0,0,tzinfo=pical.utc), datetime(2006,1,7,10,0,0,tzinfo=pical.utc)], component="VTODO")
			if len([c for c in u.children if c.name!="VTIMEZONE"])==0:
				continue
			for l in u.serialize():
				print(l)

def test_parse():
	for f in glob.glob("%s/*.ics" % os.path.dirname(__file__)):
		for c in pical.parse(open(f,"rb")):
			fp = StringIO("\r\n".join(list(c.serialize())))
			pical.parse(fp)

def test_range():
	cal = pical.parse(open("%s/google_calendar_ex1.ics" % os.path.dirname(__file__),"rb"))[0]
	q = cal.time_range(expand=[datetime(2015,4,1,tzinfo=pical.utc), datetime(2015,6,1,tzinfo=pical.utc)])
	assert len([c for c in q.children if c.name=="VEVENT"])==10
	q = cal.time_range(time_range=[datetime(2015,4,1,tzinfo=pical.utc), datetime(2015,6,1,tzinfo=pical.utc)])
	for l in q.serialize():
		print(l)
	assert len([c for c in q.children if c.name=="VEVENT"])==3

def test_eq():
	a = pical.parse(open("%s/google_calendar_ex1.ics" % os.path.dirname(__file__),"rb"))[0]
	b = pical.parse(open("%s/google_calendar_ex1.ics" % os.path.dirname(__file__),"rb"))[0]
	assert a==b, "__eq__ does not work"
	assert not a!=b, "__ne__ does not work"
	c = pical.parse(open("%s/rfc5545_3_4.ics" % os.path.dirname(__file__),"rb"))[0]
	assert a!=c, "__ne__ does not work"
	assert not a==c, "__eq__ does not work"

if __name__=="__main__":
	test_eq()
	test_parse()
	test_range()
	print("### 4791 7.8.1 ###")
	test_caldav_7_8_1()
	print("### 4791 7.8.2 ###")
	test_caldav_7_8_2()
	print("### 4791 7.8.3 ###")
	test_caldav_7_8_3()
	print("### 4791 7.8.4 ###")
	test_caldav_7_8_4()
	print("### 4791 7.8.5 ###")
	test_caldav_7_8_5()
