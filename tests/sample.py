import pical
import glob
import os.path
import logging
logging.basicConfig()

def test_parse():
	for f in glob.glob("%s/*.ics" % os.path.dirname(__file__)):
		pical.parse(open(f,"rb"))

if __name__=="__main__":
	test_parse()
