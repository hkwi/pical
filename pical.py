from datetime import datetime, date, time, timedelta, tzinfo
from functools import cmp_to_key
import base64
import operator
import re
import logging
digits = re.compile(r"^\d+$")
control = re.compile(r"[\x00-\x1F\x7F]")

try:
	str_cls = unicode
except:
	str_cls = str

def digits(sign, lower, upper):
	def inner(value):
		if ((sign and value[0] in "+-" and 0 < len(value)-1 <= len("%d" % upper))
				or (0 < len(value) <= len("%d" % upper))):
			v = int(value)
			if ((sign and lower <= -v <= upper)
					or (lower <= v <= upper)):
				return v
			else:
				raise ValueError("range error")
		else:
			raise ValueError("format length error")
	return inner

def unfold(stream):
	buf = None
	lineno = nxno = 0
	for nx in stream:
		if len(nx)>1 and nx[-2:] in (b"\r\n", "\r\n"):
			nx = nx[:-2]
		elif len(nx)>0 and nx[-1:] == "\n":
			nx = nx[:-1]
		
		nxno += 1
		if len(nx) > 0 and nx[0:1] in (" ", "\t", b" ", b"\t"):
			if buf is None:
				buf = nx
			else:
				buf += nx[1:]
		else:
			if buf is not None:
				yield buf, lineno
			lineno = nxno
			buf = nx
	
	if buf is not None:
		yield buf, lineno

def parse(stream, encoding="UTF-8"):
	logger = logging.getLogger("pical")
	comp = Component(" root", None)
	stack = [comp]
	for line,lineno in unfold(stream):
		if isinstance(line, bytes):
			line = line.decode(encoding)
		m = re.match(r"^([a-zA-Z0-9-]+)([;:])", line)
		if not m:
			logger.error("contentline name error L%d" % lineno)
		name,nx = m.groups()
		line = line[len(m.group(0)):]
		params = []
		while nx==";":
			m = re.match(r'^([a-zA-Z0-9-]+)=([^\x00-\x1F\x7F";:,]*?|"[^\x00-\x1F\x7F"]*?")([,:;])', line)
			if not m:
				logger.error("contentline param error L%d" % lineno)
			pname,pval,nx = m.groups()
			line = line[len(m.group(0)):]
			vals=[pval]
			while nx == ",":
				m = re.match(r'^([^\x00-\x1F\x7F";:,]*?|"[^\x00-\x1F\x7F"]*?")([,:;])', line)
				if not m:
					logger.error("contentline multi param error L%d" % lineno)
				pval,nx = m.groups()
				line = line[len(m.group(0)):]
				vals.append(pval)
			
			params.append((pname, Parameter.raw2native(pname, vals)))
		value = line
		
		name_upper = name.upper()
		if name_upper == "BEGIN":
			tzdb = comp.tzdb
			if tzdb is None:
				tzdb = {}
			
			sub = Component.factory(value, tzdb)
			if params:
				logger.error("component takes no parameter L%d" % lineno)
			
			comp.children.append(sub)
			stack.append(comp)
			comp = sub
		elif name_upper == "END":
			if comp.name.upper() == value.upper():
				try:
					comp.validate()
				except Exception as e:
					logger.error("%s L%d" % (e,lineno))
				comp = stack.pop()
			else:
				logger.error("END does not match with BEGIN L%d" % lineno)
		else:
			try:
				comp.parseProperty(name, value, params)
			except Exception as ex:
				logger.error("property %s value parse error: %s L%d" % (name,ex,lineno))
	
	if comp.name != " root":
		raise ValueError("missing END L%d" % lineno)
	return comp.children


class Parameter(object):
	paramQuote = "ALTREP CN DELEGATED-FROM DELEGATED-TO DIR MEMBER SENT-BY"
	
	paramOptions = {
		"CUTYPE": "INDIVIDUAL GROUP RESOURCE ROOM UNKNOWN X-",
		"ENCODING": "8BIT BASE64 X-",
		"FBTYPE": "FREE BUSY BUSY-UNAVAILABLE BUSY-TENTATIVE X-",
		"PARTSTAT": "NEEDS-ACTION ACCEPTED DECLINED TENTATIVE DELEGATED COMPLETED IN-PROCESS X-",
		"RANGE": "THISANDFUTURE THISANDPRIOR",
		"RELATED": "START END",
		"RELTYPE": "PARENT CHILD SIBLING X-",
		"ROLE": "CHAIR REQ-PARTICIPANT OPT-PARTICIPANT NON-PARTICIPANT X-",
		"RSVP": "TRUE FALSE",
		"VALUE": "BINARY BOOLEAN CAL-ADDRESS DATE DATE-TIME DURATION "
			"FLOAT INTEGER PERIOD RECUR TEXT TIME URI UTC-OFFSET X-",
	}
	
	@classmethod
	def raw2native(cls, pname, values):
		options = cls.paramOptions.get(pname,"").split()
		
		pvalues = []
		for value in values:
			if options:
				if value not in options and "X-" not in options:
					logging.getLogger("pical").warn("param %s have non-standard value" % pname)
			elif (value[0] != '"' or value[-1] != '"') and pname.upper() in cls.paramQuote.split():
				logging.getLogger("pical").warn("parameter %s was not DQUOTE" % pname)
			
			if value[0] == '"':
				pvalues.append(value[1:-1])
			else:
				pvalues.append(value)
		return pvalues
	
	@classmethod
	def native2raw(cls, pname, values):
		pvalues = []
		for value in values:
			if control.search(value) is not None:
				logging.getLogger("pical").error("parameter %s has CONTROL" % pname) # python2 may hit
			
			options = cls.paramOptions.get(pname,"").split()
			if options:
				if value not in options and "X-" not in options:
					logging.getLogger("pical").warn("param %s have non-standard value" % pname)
			
			dquote = False
			if value[0]=='"' and value[-1]=='"':
				dquote = False # already encoded
			elif '"' in value:
				logging.getLogger("pical").error("parameter %s has DQUOTE" % pname) # python2 may hit
			elif pname.upper() in cls.paramQuote.split():
				dquote = True
			else:
				for c in ";:,":
					if c in value:
						dquote = True
			
			if dquote:
				pvalues.append('"%s"' % value)
			else:
				pvalues.append(value)
		return pvalues
	
	@classmethod
	def fill(cls, name, value, params):
		def tzhook(value,params):
			if value.tzinfo and not Timezone.is_utc(value.tzinfo):
				if isinstance(value.tzinfo, Timezone):
					tzid = [value.tzinfo["TZID"]]
				else:
					base = str_cls(value.tzinfo)
					tzid = ["/"+base, base]
				
				ptzid = dict(params).get("TZID")
				if ptzid is None:
					params.append(("TZID",[tzid[0]]))
				elif ptzid[0] != tzid[0]:
					if ptzid[0] not in tzid:
						logging.getLogger("pical").warn("TZID conflict %s in %s" % (ptzid[0],tzid))
			return params
		
		vparams = list(params)
		klass = vtype_resolve(value)
		if klass in (DateTime, Time):
			vparams = tzhook(value,vparams)
		elif klass == Period:
			vparams = tzhook(value[0], vparams)
			if isinstance(value[1], datetime):
				vparams = tzhook(value[1], vparams)
		return vparams
	
class Component(object):
	valueTypes = {
		"CALSCALE": "TEXT",
		"METHOD": "TEXT",
		"PRODID": "TEXT",
		"VERSION": "TEXT",
		"ATTACH": "URI BINARY",
		"CATEGORIES": "TEXT",
		"CLASS": "TEXT",
		"COMMENT": "TEXT",
		"DESCRIPTION": "TEXT",
		"GEO": "FLOAT",
		"LOCATION": "TEXT",
		"PERCENT-COMPLETE": "INTEGER",
		"PRIORITY": "INTEGER",
		"RESOURCES": "TEXT",
		"STATUS": "TEXT",
		"SUMMARY": "TEXT",
		"COMPLETED": "DATE-TIME",
		"DTEND": "DATE-TIME DATE",
		"DUE": "DATE-TIME DATE",
		"DTSTART": "DATE-TIME DATE",
		"DURATION": "DURATION",
		"FREEBUSY": "PERIOD",
		"TRANSP": "TEXT",
		"TZID": "TEXT",
		"TZNAME": "TEXT",
		"TZOFFSETFROM": "UTC-OFFSET",
		"TZOFFSETTO": "UTC-OFFSET",
		"TZURL": "URI",
		"ATTENDEE": "CAL-ADDRESS",
		"CONTACT": "TEXT",
		"ORGANIZER": "CAL-ADDRESS",
		"RECURRENCE-ID": "DATE-TIME DATE",
		"RELATED-TO": "TEXT",
		"URL": "URI",
		"UID": "TEXT",
		"EXDATE": "DATE-TIME DATE",
		"EXRULE": "RECUR",
		"RDATE": "DATE-TIME DATE PERIOD",
		"RRULE": "RECUR",
		"ACTION": "TEXT",
		"REPEAT": "INTEGER",
		"TRIGGER": "DURATION DATE-TIME",
		"CREATED": "DATE-TIME",
		"DTSTAMP": "DATE-TIME",
		"LAST-MODIFIED": "DATE-TIME",
		"SEQUENCE": "INTEGER",
		"REQUEST-STATUS": "TEXT",
	}

	valueDelimiter = {
		"CATEGORIES": ",",
		"GEO": ";",
		"RESOURCES": ",",
		"FREEBUSY": ",",
		"EXDATE": ",",
		"RDATE": ",",
		"REQUEST-STATUS": ";",
	}

	props = dict(
		VCALENDAR = dict(
			req = "PRODID VERSION",
			once = "CALSCALE METHOD",
			),
		VEVENT = dict(
			req5545 = "DTSTAMP UID",
			once = "DTSTART"
				" CLASS CREATED DESCRIPTION GEO"
				" LAST-MODIFIED LOCATION ORGANIZER PRIORITY"
				" SEQUENCE STATUS SUMMARY TRANSP"
				" URL RECURRENCE-ID"
				" DTEND DURATION",
			many = "RRULE EXRULE"
				" ATTACH ATTENDEE CATEGORIES COMMENT"
				" CONTACT EXDATE REQUEST-STATUS RELATED-TO"
				" RESOURCES RDATE",
			),
		VTODO = dict(
			req5545 = "DTSTAMP UID",
			once = "CLASS COMPLETED CREATED DESCRIPTION"
				" DTSTART GEO LAST-MODIFIED LOCATION ORGANIZER"
				" PERCENT-COMPLETE PRIORITY RECURRENCE-ID SEQUENCE STATUS"
				" SUMMARY URL"
				" DUE DURATION",
			many = "RRULE EXRULE"
				" ATTACH ATTENDEE CATEGORIES COMMENT CONTACT"
				" EXDATE REQUEST-STATUS RELATED-TO RESOURCES"
				" RDATE",
			),
		VJOURNAL =dict(
			req5545 = "DTSTAMP UID",
			once = "CLASS CREATED DTSTART"
				" LAST-MODIFIED ORGANIZER RECURRENCE-ID SEQUENCE"
				" STATUS SUMMARY URL",
			many = "RRULE EXRULE"
				" ATTACH ATTENDEE CATEGORIES COMMENT"
				" CONTACT DESCRIPTION EXDATE RELATED-TO RDATE"
				" REQUEST-STATUS",
			),
		VFREEBUSY = dict(
			req5545 = "DTSTAMP UID",
			once = "CONTACT DTSTART DTEND DURATION"
				" ORGANIZER URL",
			many = "ATTENDEE COMMENT FREEBUSY REQUEST-STATUS",
			),
		VTIMEZONE = dict(
			key = "TZID",
			once = "LAST-MODIFIED TZURL",
			),
		DAYLIGHT = dict(
			key = "DTSTART TZOFFSETTO TZOFFSETFROM",
			many = "RRULE"
				" COMMENT RDATE TZNAME",
			),
		STANDARD = dict(
			key = "DTSTART TZOFFSETTO TZOFFSETFROM",
			many = "RRULE"
				" COMMENT RDATE TZNAME",
			),
		VALARM = dict(
			key = "ACTION TRIGGER",
			once = "DESCRIPTION SUMMARY"
				" DURATION REPEAT",
			many = "ATTENDEE"
				" ATTACH",
			),
	)
	
	def __init__(self, name, tzdb):
		self.name = name
		self.tzdb = tzdb
		self.children = []
		self.properties = []
	
	def __eq__(self, other):
		if self.__class__ != other.__class__:
			return False
		
		if self.name.upper() != other.name.upper():
			return False
		
		if sorted(self.properties) != sorted(other.properties):
			return False
		
		for a,b in ((self.children,other.children),(other.children,self.children)):
			for c1 in a:
				hit = False
				for c2 in b:
					if c1 == c2:
						hit = True
						break
				if not hit:
					return False
		
		return True
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __getitem__(self, name):
		name_upper = name.upper()
		for prop in self.properties:
			if prop[0].upper() == name_upper:
				return prop[1]
		raise KeyError("property %s not found" % name)
	
	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default
	
	def list(self, name):
		name_upper = name.upper()
		return [prop[1] for prop in self.properties if prop[0].upper() == name_upper]
	
	def key_counts(self):
		ret = {}
		for prop in self.properties:
			name_upper = prop[0].upper()
			if name_upper in ret:
				ret[name_upper] += 1
			else:
				ret[name_upper] = 1
		return ret
	
	def validate(self):
		key_counts = self.key_counts()
		info = self.props.get(self.name, {})
		for prop in info.get("key","").split():
			# system requires
			assert key_counts.get(prop,0)==1, "component %s requires property %s" % (self.name, prop)
		for prop in info.get("req","").split():
			# rfc2445 and rfc5545 requires
			if key_counts.get(prop,0)!=1:
				logging.getLogger("pical").warn("component %s requires property %s" % (self.name, prop))
		for prop in info.get("req5545","").split():
			# rfc5545 requires
			if key_counts.get(prop,0)!=1:
				logging.getLogger("pical").warn("component %s requires property %s in rfc5545" % (self.name, prop))
		for prop in info.get("once","").split():
			assert key_counts.get(prop,0)<2, "component %s property %s must not occur more than once in %s" % (self.name, prop)
		
		for name,value,params in self.properties:
			name_upper = name.upper()
			if name_upper in self.valueTypes:
				accept = False
				for constraint,props in info.items():
					if name_upper in props.split():
						accept = True
				if not accept:
					raise ValueError("property %s is not defined in component %s" % (name, self.name))
		
		self_name_upper = self.name.upper()
		if self_name_upper == "VTIMEZONE":
			assert len([c for c in self.children if c.name in "DAYLIGHT STANDARD".split()]) > 0, "VTIMEZONE must include at least one definition"
		if self_name_upper in "DAYLIGHT STANDARD".split():
			if self.list("RRULE"):
				assert self.get("DTSTART") and self.get("TZOFFSETFROM"), "DTSTART and TZOFFSETFROM must be used when generating the onset DATE-TIME values"
			for rdates in self.list("RDATE"):
				for rdate in rdates:
					if isinstance(rdate,datetime):
						assert rdate.tzinfo is None, "RDATE must be specified as a date with local time value"
		
		if self_name_upper in "VEVENT VTODO VJOURNAL DAYLIGHT STANDARD".split():
			for name in ("RRULE","EXRULE"):
				recurrs = self.list(name)
				if len(recurrs) > 1:
					logging.getLogger("pical").warn("property %s should not occur more than once" % name)
				for recur in recurrs:
					assert recur.get("FREQ"), "FREQ part is required in property %s" % name
		
		if self_name_upper == "VEVENT":
			if self.get("DTEND") and self.get("DURATION"):
				raise ValueError("either DTEND or DURATION may appear")
		elif self_name_upper == "VTODO":
			if self.get("DUE") and self.get("DURATION"):
				raise ValueError("either DUE or DURATION may appear")
		elif self_name_upper == "VALARM":
			duration = self.get("DURATION")
			repeat = self.get("REPEAT")
			if (duration is None and repeat is not None) or (duration is not None and repeat is None):
				raise ValueError("both DURATION and REPEAT must occur")
		
		if self_name_upper == "VEVENT":
			dtstart_list = self.list("DTSTART")
			if len(dtstart_list)==1:
				assert self.get("METHOD") is None, "DTSTART is REQUIRED if METHOD is not present"
			assert len(dtstart_list) < 2, "DTSTART must not occur more than once"
			dtstart = dtstart_list[0]
			if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
				dtend = self.get("DTEND")
				if dtend:
					assert isinstance(dtend, date) and not isinstance(dtend, datetime), "DTEND must be DATE value also"
				dur = self.get("DURATION")
				if dur:
					assert dur.seconds == 0, "DATE DTSTART may have only dur-day or dur-week DURATION"
		elif self_name_upper == "VTIMEZONE":
			self.tzdb[self["TZID"]] = self
		elif self_name_upper in ("DAYLIGHT", "STANDARD"):
			assert self["DTSTART"].tzinfo is None, "DTSTART in %s is local DATE-TIME value" % self.name
			for rdate in self.list("RDATE"):
				for r in rdate:
					if isinstance(r, Period):
						r = r[0]
					assert isinstance(r, datetime) and r.tzinfo is None, "RDATE in %s is local date with local time" % self.name
		elif self_name_upper == "VALARM":
			action = self.get("ACTION")
			if action=="AUDIO":
				assert key_counts.get("ATTACH",0) < 2, "AUDIO VALARM may include one ATTACH property"
			elif action=="DISPLAY":
				assert key_counts.get("DESCRIPTION",0) > 0, "DISPLAY VALARM must include DESCRIPTION"
			elif action=="EMAIL":
				assert key_counts.get("DESCRIPTION",0) > 0, "EMAIL VALARM must include DESCRIPTION"
				assert key_counts.get("SUMMARY",0) > 0, "EMAIL VALARM must include SUMMARY"
				assert key_counts.get("ATTENDEE",0) > 0, "EMAIL VALARM must include ATTENDEE"
		elif self_name_upper == "VCALENDAR":
			masters = []
			slaves = []
			for c in self.children:
				if c.get("RECURRENCE-ID") is None:
					masters.append(c)
				else:
					slaves.append(c)
			
			for comp in slaves:
				comp_name_upper = comp.name.upper()
				for c in masters:
					if c.name.upper()==comp_name_upper and c["UID"]==comp["UID"]:
						assert type(c["DTSTART"])==type(comp["RECURRENCE-ID"]), "RECURRENCE-ID type must be same with reference DTSTART type"
						break
	
	def pickTzinfo(self, tzid):
		if not tzid:
			return
		
		if tzid[0] != "/":
			tzinfo = self.tzdb.get(tzid)
			if tzinfo:
				return tzinfo
			logging.getLogger("pical").warn("TZID %s should be included" % tzid)
		else:
			tzid = tzid[1:]
		
		# contact global registry
		# pytz, icu, tzical, dateutil
		def tz1():
			import pytz
			return pytz.timezone(tzid)
		
		def tz2():
			from icu import ICUtzinfo
			return ICUtzinfo.getInstance(tzid)
		
		for f in (tz1,tz2):
			try:
				return f()
			except:
				continue
	
	def parseProperty(self, name, value, params):
		if self.name == " root":
			logging.getLogger("pical").error("no component to add to")
		
		name_upper = name.upper()
		pdic = dict(params) # NOTE: value is list
		tzinfo = self.pickTzinfo(pdic.get("TZID", [None])[0])
		acceptTypes = self.valueTypes.get(name_upper, "TEXT").split()
		selectedType = pdic.get("VALUE", acceptTypes)[0]
		if selectedType not in acceptTypes:
			logging.getLogger("pical").warn("%s not a standard VALUE parameter value" % selectedType)
			selectedType = "TEXT"
		
		typedValue = None
		delim = self.valueDelimiter.get(name_upper)
		for stype in [selectedType]+acceptTypes:
			vtype = _vtype.get(stype)
			try:
				if delim:
					typedValue = [vtype.parse(v, tzinfo) for v in value.split(delim)]
				else:
					typedValue = vtype.parse(value, tzinfo)
				break
			except Exception as e:
				pass
		
		if typedValue is None:
			raise ValueError("property %s invalid VALUE, none of %s" % (name, acceptTypes))
		
		self.properties.append((name, typedValue, params))
	
	def serialize(self):
		yield "BEGIN:%s" % self.name
		
		def tzhook(value,params):
			if value.tzinfo is None or value.tzinfo == utc or value.tzinfo.tzname(datetime.now()) == "UTC":
				pass
			elif dict(params).get("TZID") is None:
				if isinstance(value.tzinfo, Timezone):
					params.append(("TZID", [value.tzinfo["TZID"]]))
				else:
					params.append(("TZID", ["/"+str_cls(value)]))
			return params
		
		for name,value,params in self.properties:
			vparams = Parameter.fill(name, value, params)
			def build_value(value):
				klass = vtype_resolve(value)
				if klass:
					vstr = klass.build(value)
				else:
					vstr = repr(value)
				return vstr
			
			delim = self.valueDelimiter.get(name.upper())
			if delim:
				vstr = delim.join([build_value(v) for v in value])
			else:
				vstr = build_value(value)
			
			yield "%s%s:%s" % (name, "".join([";%s=%s" % (k,",".join(Parameter.native2raw(k,v))) for k,v in vparams]), vstr)
		for c in self.children:
			for s in c.serialize():
				yield s
		yield "END:%s" % self.name
	
	def clone(self, in_utc=False):
		# component is mutable, properties are immutable
		exp = Component.factory(self.name, self.tzdb)
		if in_utc:
			exp.children = [c.clone(in_utc=in_utc) for c in self.children if c.name.upper()!="VTIMEZONE"]
			for name,value,params in self.properties:
				if isinstance(value, (datetime,time)) and value.tzinfo:
					value = value.astimezone(utc)
					vparams = []
					for pname,values in params:
						if pname.upper() == "TZID":
							continue
						vparams.append((pname,values))
					params = vparams
				exp.properties.append((name, value, params))
		else:
			exp.children = [c.clone(in_utc=in_utc) for c in self.children]
			exp.properties += self.properties
		return exp
	
	@classmethod
	def factory(cls, name, tzdb):
		name_upper = name.upper()
		if name_upper == "VCALENDAR":
			self = Calendar(name, tzdb)
		elif name_upper == "VTIMEZONE":
			self = Timezone(name, tzdb)
		else:
			self = cls(name, tzdb)
		return self

class Overlap(object):
	def __init__(self, time_range, floating_tz=None):
		self.time_range = time_range
		self.floating_tz = floating_tz
		self.dtcmp = vdatetime_cmp(floating_tz)
	
	def __call__(self, dtstart, dtend, obj):
		# @dtstart, @dtend is the timespec we want to test.
		# @obj is supplementaly information object, and may vary with components
		# @return is the filtered object or None without overlap
		return getattr(self, obj.name.lower())(dtstart, dtend, obj)
	
	def vevent(self, dtstart, dtend, obj):
		start, end = self.time_range
		dtcmp = self.dtcmp
		
		ret = True
		if dtend:
			if start:
				if isinstance(dtend, timedelta): # DURATION
					if dtend > timedelta(seconds=0):
						ret &= dtcmp(start, dtstart+dtend) < 0
					else:
						ret &= dtcmp(start, dtstart) <= 0
				else:
					ret &= dtcmp(start, dtend) < 0
			if end:
				ret &= dtcmp(end, dtstart) > 0
		elif isinstance(dtstart, datetime):
			if start:
				ret &= dtcmp(start, dtstart) <= 0
			if end:
				ret &= dtcmp(end, dtstart) > 0
		else:
			if start:
				ret &= dtcmp(start, dtstart+timedelta(1)) < 0
			if end:
				ret &= dtcmp(end, dtstart) > 0
		
		if ret:
			return obj
	
	def vtodo(self, dtstart, dtend, obj):
		start, end = self.time_range
		dtcmp = self.dtcmp
		
		ret = True
		if dtstart:
			if dtend:
				if isinstance(dtend, timedelta): # DURATION
					if start:
						ret &= dtcmp(start,dtstart+dtend)<=0
					if end:
						ret &= dtcmp(end>dtstart) or dtcmp(end,dtstart+dtend)>=0
				else:
					if start:
						ret &= dtcmp(start,dtend)<0 or dtcmp(start,dtstart)<=0
					if end:
						ret &= dtcmp(end,dtstart)>0 or dtcmp(end,dtend)>=0
			else:
				if start:
					ret &= dtcmp(start,dtstart)<=0
				if end:
					ret &= dtcmp(end,dtstart)>0
		else:
			completed = obj.get("COMPLETED")
			created = obj.get("CREATED")
			if completed:
				if created:
					if start:
						ret &= dtcmp(start,created)<=0 or dtcmp(start,completed)<=0
					if end:
						ret &= dtcmp(end,created)>=0 or dtcmp(end,completed)>=0
				else:
					if start:
						ret &= dtcmp(start,completed)<=0
					if end:
						ret &= dtcmp(end,completed)>=0
			elif created:
				if end:
					ret &= end > created
		if ret:
			return obj
	
	def vjournal(self, dtstart, dtend, obj):
		start, end = self.time_range
		dtcmp = self.dtcmp
		
		ret = True
		if dtstart:
			if start:
				if isinstance(dtstart,datetime):
					ret &= dtcmp(start,dtstart)<=0
				else:
					ret &= dtcmp(start,dtstart+timedelta(1))<0
			if end:
				ret &= dtcmp(end,dtstart)>0
		else:
			ret = False
		
		if ret:
			return obj
	
	def vfreebusy(self, dtstart, dtend, obj):
		start, end = self.time_range
		dtcmp = self.dtcmp
		
		ret = True
		freebusy = obj.list("FREEBUSY")
		if dtstart and dtend:
			if start:
				ret &= dtcmp(start,dtend)<=0
			if end:
				ret &= dtcmp(end,dtstart)>0
		elif freebusy:
			fbs_hit = False
			for fbs in freebusy:
				for fb in fbs:
					fb_hit = True
					if start:
						fb_hit &= dtcmp(start,fb[1])<0
					if end:
						fb_hit &= dtcmp(end,fb[0])>0
					if fb_hit:
						fbs_hit = True
			if not fbs_hit:
				ret = False
		else:
			ret = False
		
		return obj
	
	def valarm(self, dtstart, dtend, obj):
		# dtstart, dtend is the container's value
		start, end = self.time_range
		dtcmp = self.dtcmp
		
		for name,value,params in obj.properties:
			if name.upper()!="TRIGGER":
				continue
			
			if isinstance(value, timedelta):
				rel = dict(params).get("RELATED",["START"])[0].upper()
				if rel == "START":
					trigger_time = dtstart + value
				elif rel == "END":
					if isinstance(dtend, timedelta):
						trigger_time = dtstart + dtend + value
					elif isinstance(dtend, datetime):
						trigger_time = dtend + value
					elif isinstance(dtend, date):
						trigger_time = datetime.combine(dtend,time(tzinfo=self.floating_tz)) + value
					else:
						raise ValueError("unknown end value type")
				else:
					raise ValueError("unknown RELATED value")
			else:
				trigger_time = value
			
			def trigger_cmp(dt):
				ret = True
				if start:
					ret &= dtcmp(start, dt)<=0
				if end:
					ret &= dtcmp(end, dt)>0
				if ret:
					return True
			
			if trigger_cmp(trigger_time):
				return True
			
			duration = obj.get("DURATION")
			if duration:
				for count in range(obj.get("REPEAT",0)):
					dt = trigger_time + duration*(count+1)
					if trigger_cmp(dt):
						return True
		return False

class Calendar(Component):
	def time_filter(self, fb_range=None, floating_tz=None):
		dtcmp = vdatetime_cmp(floating_tz)
		exp = self.clone()
		for c in exp.children:
			if c.name.upper() == "VFREEBUSY" and fb_range:
				start,end = fb_range
				properties = []
				for name,value,params in c.properties:
					if name.upper() == "FREEBUSY":
						for fb in value:
							fb_hit = True
							if start:
								if isinstance(fb[1],datetime):
									fb_hit &= dtcmp(start,fb[1])<0
								else:
									fb_hit &= dtcmp(start,fb[0]+fb[1])<0
							if end:
								fb_hit &= dtcmp(end,fb[0])>0
							if fb_hit:
								properties.append((name,value,params))
								break
					else:
						properties.append((name,value,params))
				c.properties = properties
		return exp
	
	def time_range(self, component=None, recur=None, expand=None, time_range=None, alarm_range=None, floating_tz=None):
		'''
		time-range family that requires testing effective component timespec.
		`time_range` keyword argument for time-range, and `recur` for limit-recurrence-set,
		`expand` for expand, `alarm_range` for time-range spec in alarm.
		
		For limit-freebusy-set, use time_filter method.
		'''
		if recur and expand:
			raise NotImplementedError("either limit-recurrence-set or expand could be specified")
		
		for start_end in (recur, expand):
			if start_end is None:
				continue
			start,end = start_end
			assert start and end, "both start and end is required for limit-recurrence-set or expand"
			assert end > start, "end must be greater than start"
			for dt in start_end:
				assert isinstance(dt,datetime) and dt.tzinfo, "start, end must be a datetime in UTC"
		
		for start_end in (time_range, alarm_range):
			if start_end is None:
				continue
			start,end = start_end
			assert start or end, "start and or end is required for time-range"
			if start and end:
				assert end > start, "end must be greater than start"
			for dt in start_end:
				if dt:
					assert isinstance(dt,datetime) and dt.tzinfo, "start, end must be a datetime in UTC"
		
		def expanded(dtstart,dtend,base,upon):
			comp_name_upper = None
			if base:
				comp_name_upper = base.name.upper()
			elif upon:
				comp_name_upper = upon.name.upper()
			
			def value_param(name, value, params):
				vname = None
				tnames = self.valueTypes[name.upper()].split()
				if "TEXT" not in tnames:
					klass = vtype_resolve(value)
					
					resolved = False
					for idx,tname in enumerate(tnames):
						if klass == _vtype[tname]:
							resolved = True
							if idx: # non-default case
								vname = tname
					if not resolved:
						for k,v in _vtype.items():
							if v == klass:
								vname = k
								logging.getLogger("pical").error("property %s is using irregular value type %s" % (name,vname))
				params = [param for param in params if param[0].upper()!="VALUE"]
				if vname:
					params.append(("VALUE",[vname]))
				return params
			
			override = {}
			# RECURRENCE-ID
			if base.get("DTSTART") != dtstart:
				override["RECURRENCE-ID"] = dtstart
			# DTSTART
			if dtstart is not None:
				override["DTSTART"] = dtstart
			if upon and upon.get("DTSTART"):
				override["DTSTART"] = upon["DTSTART"] + (dtstart - upon["RECURRENCE-ID"]) # for RANGE parameter
			# DTEND
			if dtend is None:
				dtend = base.get("DURATION",base.get("DTEND",base.get("DUE")))
				if base.get("DTSTART") and not isinstance(dtend, timedelta):
					dtend = dtstart + (dtend - base["DTSTART"])
			if upon:
				t = upon.get("DURATION",upon.get("DTEND",upon.get("DUE")))
				if t:
					if isinstance(t, timedelta):
						dtend = t
					elif upon.get("DTSTART"):
						dtend = t + (dtstart - upon["RECURRENCE-ID"])
					else:
						logging.getLogger("pical").error("override failure: DTEND/DUE specified without DTSTART")
			if dtend:
				if isinstance(dtend, timedelta):
					override["DURATION"] = dtend
				elif comp_name_upper == "VTODO":
					override["DUE"] = dtend
				else:
					override["DTEND"] = dtend
			
			if dtstart == base.get("DTSTART") and not expand:
				exp = base
			else:
				exp = base.clone()
				# properties
				def merge(a, b):
					props = []
					a = list(a)
					b = list(b)
					exclusives = [("DURATION","DTEND","DUE"),]
					for name,value,params in a:
						name_upper = name.upper()
						replaced = False
						exclusive = False
						for ex in exclusives:
							if not replaced and name_upper in ex:
								exclusive = True
								for prop in b:
									if not replaced and prop[0] in ex:
										b.remove(prop)
										replaced = True
										props.append(prop)
										break
						if not exclusive:
							for prop in b:
								if not replaced and prop[0].upper()==name_upper:
									b.remove(prop)
									replaced = True
									props.append(prop)
									break
						if not replaced:
							props.append((name,value,params))
					for prop in b:
						props.append(prop)
					return props
				
				props = list(base.properties)
				if upon:
					props = merge(props, upon.properties)
				props = merge(props, [(name,value,value_param(name,value,[])) for name,value in override.items()])
				exp.properties = [p for p in props if p[0] not in ("RRULE","EXRULE","RDATE","EXDATE")]
				
				# subcomponent(VALARM)
				children = [c.clone() for c in base.children]
				if upon and upon.children:
					children += [c.clone() for c in upon.children]
				for c in children:
					for idx,prop in enumerate(c.properties):
						if prop[0]=="TRIGGER" and isinstance(prop[1],datetime):
							delta = dtstart - base["DTSTART"]
							if upon:
								delta += (upon["DTSTART"] - upon["RECURRENCE-ID"])
							c.properties[idx] = (prop[0], prop[1]+delta, params)
				exp.children = children
			
			return exp
		
		def filter_passed(obj):
			dtstart = obj.get("DTSTART")
			dtend = comp_dtend(obj)
			
			if alarm_range:
				alarm_hit = False
				children = []
				for c in obj.children:
					if c.name.upper() != "VALARM":
						children.append(c)
						continue
					if Overlap(alarm_range, floating_tz)(dtstart,dtend,c):
						children.append(c)
						alarm_hit = True
				
				def filtered_alarms():
					if len(children) == (obj.children):
						return obj
					exp = obj.clone()
					exp.children = children
					return exp
				
				if alarm_hit:
					if time_range:
						if Overlap(time_range, floating_tz)(dtstart,dtend,obj):
							return filtered_alarms()
					else:
						return filtered_alarms()
			elif time_range:
				if Overlap(time_range, floating_tz)(dtstart,dtend,exp):
					return obj
			else:
				return obj
		
		if recur is None and expand is None and time_range is None and alarm_range is None:
			return self
		
		open_end = True
		if recur is None and expand is None:
			if time_range and time_range[1]:
				open_end = False
			if alarm_range and alarm_range[1]:
				open_end = False
		else:
			open_end = False
		
		found = []
		for cname in "VEVENT VTODO VJOURNAL VFREEBUSY".split():
			if component and component != cname:
				continue
			
			uids = set([c.get("UID") for c in self.children if c.name.upper()==cname])
			
			if open_end:
				for base in self.children:
					if cname != base.name.upper():
						continue
					ulim_rrule = sorted([sorted(recurr.items()) for recurr in base.list("RRULE")
						if recurr.get("UNTIL") is None and recurr.get("COUNT") is None])
					ulim_erule = sorted([sorted(recurr.items()) for recurr in base.list("EXRULE")
						if recurr.get("UNTIL") is None and recurr.get("COUNT") is None])
					
					if ulim_rrule and ulim_rrule!=ulim_erule:
						uid = base.get("UID")
						if uid is None:
							continue
						uids.remove(uid)
						
						if base not in found:
							found.append(base)
						
						limited = []
						for upon in self.children:
							if upon.get("RECURRENCE-ID") is None or cname!=upon.name.upper() or upon["UID"]!=uid:
								continue
							
							# RANGE THISANDFUTURE will be always included
							future = False
							for name,value,params in rmod.properties:
								if name.upper() == "RECURRENCE-ID" and dict(params).get("RANGE")=="THISANDFUTURE":
									if upon not in found:
										found.append(upon)
									future = True
							if future:
								continue
							
							limited.append(upon)
						
						# check for starting
						if not limited:
							break
						scan_limit = sorted([c["RECURRENCE-ID"] for c in limited], key=vdatetime_cmp(floating_tz))[-1]
						scanner = self.scan_uid(cname, uid, floating_tz)
						while len(limited):
							dtstart,dtend,_,upon = next(scanner)
							if dtstart > scan_limit:
								break
							# assert base2 == base
							if upon in limited:
								if filter_passed(dtstart,dtend,base,upon):
									found.append(upon)
									limited.remove(upon)
			
			merger = Merger(key=cmp_to_key(vdatetime_cmp(floating_tz)))
			for uid in uids:
				merger.add(self.scan_uid(cname, uid, floating_tz))
			
			for (dtstart,dtend,base,upon), in merger():
				if dtstart and vdatetime_cmp(floating_tz)(dtstart,end) >0:
					break
				elif dtend and vdatetime_cmp(floating_tz)(dtend,end) >0:
					break
				
				exp = expanded(dtstart,dtend,base,upon)
				if recur:
					recur_overlap = Overlap(recur, floating_tz)
					if not recur_overlap(dtstart,dtend,base) and not recur_overlap(exp.get("DTSTART"), comp_dtend(exp), exp):
						continue
				if expand:
					if not Overlap(expand, floating_tz)(exp.get("DTSTART"), comp_dtend(exp), exp):
						continue
				
				obj = filter_passed(exp)
				if obj:
					if expand:
						if obj not in found:
							found.append(obj)
					else:
						if base not in found:
							found.append(base)
						if upon and upon not in found:
							found.append(upon)
		
		cal = Calendar(self.name, self.tzdb)
		cal.children = [c for c in self.children if c.name.upper()=="VTIMEZONE"]
		cal.children += found
		cal.properties += self.properties
		return cal
	
	def scan(self, component_name, floating_tz=None):
		# yields (onset_dtstart, duration_or_dtend?, generator_component, modifier_component?)
		uids = set()
		for c in self.children:
			if c.name.upper() != component_name.upper():
				continue
			uids.add(c["UID"])
		
		merger = Merger(key=cmp_to_key(vdatetime_cmp(floating_tz)))
		for uid in uids:
			merger.add(self.scan_uid(component_name, uid))
		
		for m in merger():
			yield m[0]
	
	def scan_uid(self, component_name, uid, floating_tz=None):
		# yields (onset_dtstart, duration_or_dtend?, generator_component, modifier_component?)
		rbases = []
		rmods = []
		for c in self.children:
			if c.name.upper() == component_name.upper() and c["UID"]==uid:
				if c.get("RECURRENCE-ID") is None:
					rbases.append(c)
				else:
					rmods.append(c)
		
		if not rbases: # already expanded
			for r in sorted(rmods, key=operator.itemgetter("DTSTART")):
				yield r.get("DTSTART"), None, r, None
		
		# yields (onset_dtstart, duration_or_dtend?, generator_component, modifier_component?)
		combined = Merger(key=cmp_to_key(vdatetime_cmp(floating_tz)))
		for rbase in rbases:
			# yields (onset_dtstart, duration_or_dtend?)
			setter = Merger(key=cmp_to_key(vdatetime_cmp(floating_tz)))
			unsetter = Merger(key=cmp_to_key(vdatetime_cmp(floating_tz)))
			
			for key,m in (("RDATE", setter), ("EXDATE", unsetter)):
				for values in rbase.list(key):
					dates = []
					for value in values:
						if isinstance(value, Period):
							dates.append(value)
						else:
							dates.append((value, None))
					
					m.add(iter(dates), rbase)
			
			dtstart = rbase.get("DTSTART")
			def dual(gen):
				for v in gen:
					if isinstance(v, Duration):
						yield v
					else:
						yield (v, None)
			
			for recur in rbase.list("EXRULE"):
				unsetter.add(dual(recur.expand(dtstart)), rbase)
			
			values = rbase.list("RRULE")
			if values:
				for recur in values:
					setter.add(dual(recur.expand(dtstart)), rbase)
			else:
				setter.add(dual(iter([dtstart])), rbase)
			
			def filtered(setter, unsetter):
				unset = None
				try:
					(udset,_),_ = next(unsetter)
				except StopIteration:
					unset = None
				
				for (dtstart,dtend),rbase in setter:
					if unset is not None:
						while unset < dtstart:
							try:
								(unset,_),_ = next(unsetter)
							except StopIteration:
								unset = None
								break
					
					if unset is None or dtstart != unset:
						yield dtstart,dtend,rbase
			
			# put in running status
			combined.add(filtered(setter(), unsetter()))
		
		combined = combined()
		for (dtstart, dtend, rbase), in combined:
			def lookup_modifier(dttest):
				for rmod in rmods:
					for name,value,params in rmod.properties:
						if name.upper() == "RECURRENCE-ID":
							r = dict(params).get("RANGE",[""])[0].upper()
							if r=="THISANDFUTURE":
								if dttest >= value:
									return rmod
							elif r=="THISANDPRIOR":
								if dttest <= value:
									return rmod
							else:
								if dttest == value:
									return rmod
				return None
			
			yield dtstart, dtend, rbase, lookup_modifier(dtstart)
	
	def freebusy_merge(self, comp):
		fb = None
		for c in self.children:
			if c.name.upper() == "VFREEBUSY":
				fb = c
				break
		
		if fb is None:
			fb = Component.factory("VFREEBUSY", self.tzdb)
			self.children.append(fb)
		
		comp_name_upper = comp.name.upper()
		if comp_name_upper == "VCALENDAR":
			for c in comp.children:
				self.freebusy_merge(c)
		elif comp_name_upper == "VEVENT":
			transp = comp.get("TRANSP", "OPAQUE").upper()
			status = comp.get("STATUS", "CONFIRMED").upper()
			fbtype = None
			if transp == "OPAQUE":
				if status == "CONFIRMED":
					fbtype = None
				elif status == "CANCELLED":
					fbtype = "FREE"
				elif status == "TENTATIVE":
					fbtype = "BUSY-TENTATIVE"
				else:
					fbtype = None
			elif transp == "TRANSPARENT":
				if status in "CONFIRMED CANCELLED TENTATIVE".split() or status.startswith("X-"):
					fbtype = "FREE"
			else:
				raise ValueError("TRANSP is OPAQUE or TRANSPARENT")
		
			if fbtype != "FREE":
				start = comp.get("DTSTART")
				end = comp.get("DTEND",
					comp.get("DURATION"))
				params = []
				if fbtype != None:
					params.append(("FBTYPE",[fbtype]))
				fb.properties.append(("FREEBUSY", [Period((start, end))], params))
		elif comp_name_upper == "VFREEBUSY":
			for name,value,params in comp.properties:
				if name.upper()=="FREEBUSY" and dict(params).get("FBTYPE","BUSY") != "FREE":
					fb.properties.append((name,value,params))

class Timezone(tzinfo, Component):
	def utcoffset(self, dt):
		comp = self.scan(dt)
		if comp:
			return comp["TZOFFSETTO"].utcoffset(dt)
		else:
			return timedelta(0)
	
	def dst(self, dt):
		comp = self.scan(dt)
		if comp and comp.name.upper() == "DAYLIGHT":
			return self.utcoffset()
		else:
			return timedelta(0)
	
	def tzname(self, dt):
		comp = self.scan(dt)
		if comp:
			return comp.get("TZNAME", self["TZID"])
	
	def scan(self, dt):
		merger = Merger()
		naive_mode = False
		if dt.tzinfo is None or dt.tzinfo == self:
			naive_mode = True
		
		for c in self.children:
			if c.name.upper() not in ("DAYLIGHT", "STANDARD"):
				continue
			
			dtstart = c["DTSTART"]
			if naive_mode:
				tzoffset = None
				dt = dt.replace(tzinfo = None)
			else:
				tzoffset = c["TZOFFSETFROM"]
				dtstart = dtstart.replace(tzinfo=tzoffset)
			
			for rdate in c.list("RDATE"):
				rdates = []
				for r in rdate:
					if isinstance(r, Period):
						r = r[0]
					rdates.append(r.replace(tzinfo=tzoffset))
				
				merger.add(iter(rdates), c)
			
			recur = c.get("RRULE")
			if recur:
				merger.add(recur.expand(dtstart), c)
			else:
				merger.add(iter([dtstart]), c)
		
		data = None
		for mdt,d in merger():
			if dt < mdt:
				break
			else:
				data = d
		return data
	
	@classmethod
	def is_utc(cls, info):
		if info and (info == utc
				or info.tzname(datetime.now()) == "UTC"):
			return True
		return False

## Property Value Data Types
_vtype = {}
def vtype(name):
	def register(klass):
		_vtype[name] = klass
		return klass
	return register

def vtype_resolve(value):
	if value is True or value is False:
		return Boolean
	elif isinstance(value, tuple(_vtype.values())):
		return value.__class__
	elif isinstance(value,str_cls):
		return Text
	elif isinstance(value,(bytes,bytearray)):
		return Binary
	elif isinstance(value,datetime):
		return DateTime
	elif isinstance(value,date):
		return Date
	elif isinstance(value,time):
		return Time
	elif isinstance(value,timedelta):
		return Duration
	elif isinstance(value,tzinfo):
		return UtcOffset
	elif isinstance(value,float):
		return Float
	elif isinstance(value,int):
		return Integer
	elif (isinstance(value,tuple) and len(value)==2 
			and isinstance(value[0],datetime) and isinstance(value[1],(datetime,timedelta))):
		return Period

def rich_eq(cls):
	cls.__eq__ = lambda self,other: cls.build(self) == vtype_resolve(other).build(other)
	cls.__ne__ = lambda self,other: cls.build(self) != vtype_resolve(other).build(other)
	return cls

@vtype("BINARY")
class Binary(bytes):
	@classmethod
	def parse(cls, value, tzinfo):
		self = cls(base64.decodestring(value))
		return self
	
	@classmethod
	def build(cls, self):
		return base64.encodestring(self).replace("\n","")

@vtype("BOOLEAN")
class Boolean(object):
	@classmethod
	def parse(cls, value, tzinfo):
		v = value.upper()
		if v == "TRUE":
			return True
		elif v == "FALSE":
			return False
		else:
			raise ValueError("BOOLEAN value takes TRUE or FALSE")
	
	@classmethod
	def build(cls, self):
		if self:
			return "TRUE"
		else:
			return "FALSE"

@vtype("CAL-ADDRESS")
class CalAddress(str_cls):
	@classmethod
	def parse(cls, value, tzinfo):
		self = cls(value)
		return self
	
	@classmethod
	def build(cls, self):
		return self

@rich_eq
@vtype("DATE")
class Date(date):
	pattern = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
	@classmethod
	def parse(cls, value, tzinfo):
		m = cls.pattern.match(value)
		if not m:
			raise TypeError("DATE value format error")
		year,month,mday = tuple(map(int, m.groups()))
		self = date.__new__(cls, year, month, mday)
		return self
	
	@classmethod
	def build(cls, self):
		return "%04d%02d%02d" % (self.year, self.month, self.day)

@rich_eq
@vtype("DATE-TIME")
class DateTime(datetime):
	leap = 0
	@classmethod
	def parse(cls, value, tzinfo):
		pair = value.split("T", 1)
		if len(pair) < 2:
			raise ValueError("DATE-TIME format error")
		date = Date.parse(pair[0], tzinfo)
		time = Time.parse(pair[1], tzinfo)
		self = datetime.__new__(cls, date.year, date.month, date.day,
			time.hour, time.minute, time.second, tzinfo=time.tzinfo)
		self.leap = time.leap
		return self
	
	@classmethod
	def build(cls, self):
		if isinstance(self,DateTime) and self.leap:
			base = self.strftime("%Y%m%dT%H%M60")
		else:
			base = self.strftime("%Y%m%dT%H%M%S")
		
		if Timezone.is_utc(self.tzinfo):
			base += "Z"
		
		return base


@rich_eq
@vtype("DURATION")
class Duration(timedelta):
	pattern = re.compile(r"^(?P<sign>\+?|-)?P"
		r"((?P<days>\d+)D)?"
		r"(T((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?)?"
		r"((?P<weeks>\d+)W)?$")
	@classmethod
	def parse(cls, value, tzinfo):
		m = cls.pattern.match(value)
		if not m:
			raise ValueError("DURATION format error")
		obj = m.groupdict()
		tmspec = obj["days"] or obj["hours"] or obj["minutes"] or obj["seconds"]
		if obj["weeks"] and tmspec:
			raise ValueError("DURATION format invalid spec error")
		if not obj["weeks"] and not tmspec:
			raise ValueError("DURATION format no spec error")
		
		delta_args = {}
		sign = 1
		if obj.get("sign") == "-":
			sign = -1
		for k,v in obj.items():
			if k!="sign" and v:
				delta_args[k] = sign*int(v)
		self = timedelta.__new__(cls, **delta_args)
		return self

	@classmethod
	def build(cls, self):
		parts = []
		if self < timedelta(0):
			parts.append("-")
			self = -self
		parts.append("P")
		if self.days == 0:
			pass
		elif self.days%7==0:
			parts.append("%dW" % (self.days//7,))
		else:
			parts.append("%dD" % self.days)
		if self.seconds > 0:
			parts.append("T")
			if self.seconds//3600:
				parts.append("%dH" % (self.seconds//3600,))
			if (self.seconds//60)%60:
				parts.append("%dM" % ((self.seconds//60)%60,))
			if self.seconds%60:
				parts.append("%dS" % (self.seconds%60,))
		return "".join(parts)

@vtype("FLOAT")
class Float(float):
	pattern = re.compile(r"^(\+?|-)\d+(\.\d+)?$")
	@classmethod
	def parse(cls, value, tzinfo):
		if not cls.pattern.match(value):
			raise ValueError("FLOAT format error")
		self = float.__new__(cls, value)
		return self
	
	@classmethod
	def build(cls, self):
		return "%f" % self

@vtype("INTEGER")
class Integer(int):
	pattern = re.compile(r"^(\+?|-)\d+$")
	@classmethod
	def parse(cls, value, tzinfo):
		if not cls.pattern.match(value):
			raise ValueError("INTEGER format error")
		self = int.__new__(cls, value)
		return self
	
	@classmethod
	def build(cls, self):
		return "%d" % self

@rich_eq
@vtype("PERIOD")
class Period(tuple):
	@classmethod
	def parse(cls, value, tzinfo):
		pair = value.split("/", 1)
		start = DateTime.parse(pair[0], tzinfo)
		try:
			self = tuple.__new__(cls, (start, DateTime.parse(pair[1], tzinfo)))
		except:
			self = tuple.__new__(cls, (start, Duration.parse(pair[1], tzinfo)))
		return self
	
	@classmethod
	def build(cls, self):
		if isinstance(self[1],timedelta):
			pair = (DateTime.build(self[0]), Duration.build(self[1]))
		else:
			pair = (DateTime.build(self[0]), DateTime.build(self[1]))
		return "%s/%s" % pair

@rich_eq
@vtype("RECUR")
class Recur(object):
	freq = ("SECONDLY", "MINUTELY", "HOURLY", "DAILY", "WEEKLY", "MONTHLY", "YEARLY")
	weekday = "MO TU WE TH FR SA SU".split()
	ranges = dict( # (TEST_NEGATIVE,LOWER,UPPER)
		BYSECOND = (False,0,59),
		BYMINUTE = (False,0,59),
		BYHOUR = (False,0,23),
		BYWEEKNO = (True,1,53),
		BYMONTHDAY = (True,1,31),
		BYYEARDAY = (True,1,366),
		BYMONTH = (False,1,12),
		BYSETPOS = (True,1,366)
	)
	
	def items(self):
		return tuple(self._items)
	
	def __getitem__(self, key):
		key_upper = key.upper()
		for item in self._items:
			if item[0].upper() == key_upper:
				return item[1]
		raise KeyError("parameter %s not found" % key)
	
	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default
	
	@classmethod
	def parse(cls, value, tzinfo):
		items = []
		for k,v in [kv.split("=") for kv in value.split(";")]:
			k_upper = k.upper()
			if k_upper == "FREQ":
				if v.upper() not in cls.freq:
					raise ValueError("FREQ parameter value error")
				items.append((k,v))
			elif k_upper in ("COUNT","INTERVAL"):
				items.append((k,int(v)))
			elif k_upper in cls.ranges:
				items.append((k,list(map(digits(*cls.ranges[k_upper]), v.split(",")))))
			elif k_upper == "UNTIL":
				try:
					items.append((k,Date.parse(v, tzinfo)))
				except:
					items.append((k,DateTime.parse(v, tzinfo)))
			elif k_upper == "BYDAY":
				values = v.split(",")
				list(map(digits(True,1,366), [v[:-2] for v in values if len(v)!=2]))
				for v in values:
					if v[-2:] not in cls.weekday:
						raise ValueError("BYDAY parameter error")
				items.append((k,values))
			elif k_upper == "WKST":
				if v not in cls.weekday:
					raise ValueError("WKST parameter error")
				items.append((k,v))
			else:
				items.append((k,v))
		self = cls()
		self._items = items
		return self
	
	@classmethod
	def build(cls, self):
		parts = []
		for k,v in self._items:
			part = [k]
			k_upper = k.upper()
			if k_upper=="FREQ":
				part.append(v)
			elif k_upper in ("COUNT","INTERVAL"):
				part.append("%d" % v)
			elif k_upper in cls.ranges:
				part.append(",".join(["%d" % s for s in v]))
			elif k_upper == "UNTIL":
				if isinstance(v,datetime):
					v = DateTime.build(v)
				else:
					v = Date.build(v)
				part.append(v)
			elif k_upper in ("BYDAY", "WKST"):
				part.append(",".join(v))
			else:
				part.append(v)
			parts.append("=".join(part))
		return ";".join(parts)
	
	def expand(self, dtstart, floating_tz=None):
		if floating_tz is None:
			floating_tz = utc
		weeks = ("MO","TU","WE","TH","FR","SA","SU")
		context = dict(setno=0)
		
		freq = self.get("FREQ", "").upper()
		
		def until(src, until):
			for value in src:
				flag = False
				if isinstance(value, datetime):
					if isinstance(until, datetime):
						if value.tzinfo is None:
							if until.tzinfo is None:
								flag = value <= until
							else:
								# rfc2445 backward compatibility
								flag = value.replace(tzinfo=floating_tz) <= until
						else:
							if until.tzinfo is not None:
								flag = value <= until
					else:
						raise ValueError("DTSTART and UNTIL type mismatch")
				elif isinstance(value, date):
					if isinstance(until, datetime):
						# rfc2445 backward compatibility
						flag = value <= until.date()
					elif isinstance(until, date):
						flag = value <= until
					else:
						raise ValueError("UNTIL invalid type")
				
				if flag:
					yield value
				else:
					break
	
		def count(src, part):
			for _ in range(part):
				yield next(src)
	
		def bysetpos(src, part):
			setpos = context["setno"]
			values = []
			for value in src:
				if setpos != context["setno"]:
					scans = set()
					for pos in part:
						try:
							if pos > 0:
								scans.add(values[pos-1])
							else:
								scans.add(values[pos])
						except IndexError:
							pass
					
					for v in sorted(scans):
						yield v
					
					setpos = context["setno"]
					values = [value]
				else:
					values.append(value)
		
		def bysecond(src, part):
			if freq == "SECONDLY":
				while True:
					value = next(src)
					if value.second in part:
						yield value
					# XXX: add leap time support
			else:
				# datetime module does not support leap time
				nonleap = set([p for p in part if 0<=p<=59])
				if 60 in part:
					nonleap.add(59)
				
				part = sorted(nonleap)
				value = next(src)
				for p in part:
					if p >= value.second:
						yield value.replace(second=p)
				
				for value in src:
					for p in part:
						yield value.replace(second=p)
		
		def byminute(src, part):
			if freq in ("SECONDLY", "MINUTELY"):
				for value in src:
					if value.minute in part:
						yield value
			else:
				part = sorted(set([p for p in part if 0<=p<=59]))
				value = next(src)
				for p in part:
					if p >= value.minute:
						yield value.replace(minute=p)
			
				for value in src:
					for p in part:
						yield value.replace(minute=p)
		
		def byhour(src, part):
			if freq in ("SECONDLY","MINUTELY","HOURLY"):
				for value in src:
					if value.hour in part:
						yield value
			else:
				part = sorted(set([p for p in part if 0<=p<=23]))
				value = next(src)
				for p in part:
					if p >= value.hour:
						yield value.replace(hour=p)
			
				for value in src:
					for p in part:
						yield value.replace(hour=p)
	
		def byday(src, part):
			def weekday_expand(value, weekday, in_year):
				if in_year:
					start = value.replace(month=1, day=1)
					end = (start + timedelta(400)).replace(month=1, day=1)
					limit = lambda x: x.year==value.year
				else:
					start = value.replace(day=1)
					end = (start + timedelta(40)).replace(day=1)
					limit = lambda x: x.month==value.month
				
				base = (end - start).days // 7
				xtra = (end.weekday() - start.weekday()) % 7
				if weekday in [(start.weekday()+o) % 7 for o in range(xtra)]:
					base += 1
				
				values = []
				cur = start + timedelta(days=(weekday - start.weekday())%7)
				for N in range(base):
					value = cur + timedelta(weeks=N)
					if limit(value):
						values.append(value)
				
				return values
		
			def p_expand(value, p, in_year):
				scan = weekday_expand(value, weeks.index(p[-2:]), in_year)
				if len(p)==2:
					return scan
				else:
					offset = int(p[:-2])
					if 0 <= offset-1 < len(scan):
						return [scan[offset-1]]
					elif -len(scan) <= offset < 0:
						return [scan[offset]]
				return []
		
			def part_expand(value, in_year):
				scans = set()
				for p in part:
					scans.update(p_expand(value, p, in_year))
				return sorted(scans)
		
			def part_limit(value, in_year):
				if weeks[value.weekday()] in part:
					return True
			
				for p in part:
					if len(p)!=2 and value in p_expand(value, p, in_year):
						return True
			
				return False
			
			if freq == "WEEKLY":
				wkst = weeks.index(self.get("WKST", "MO").upper())
				part = sorted([(weeks.index(p)-wkst)%7 for p in part if len(p)==2])
				
				value = next(src)
				wd = (value.weekday() - wkst) % 7
				for p in part:
					if p >= wd:
						yield value + timedelta(p - wd)
				
				for value in src:
					wd = (value.weekday() - wkst) % 7
					for p in part:
						yield value + timedelta(p - wd)
		
			elif freq == "MONTHLY":
				if self.get("BYMONTHDAY"):
					# limit
					for value in src:
						if part_limit(value, False):
							yield value
				else:
					# special expand
					value = next(src)
					for v in part_expand(value, False):
						if v >= value:
							yield v
				
					for value in src:
						for v in part_expand(value, False):
							yield v
		
			elif freq == "YEARLY":
				in_year = True
				if self.get("BYMONTH"):
					in_year = False
			
				if self.get("BYYEARDAY") or self.get("BYMONTHDAY"):
					# limit
					for value in src:
						if part_limit(value, in_year):
							yield value
				else:
					# special expand
					value = next(src)
					for v in part_expand(value, in_year):
						if v >= value:
							yield v
					
					for value in src:
						for v in part_expand(value, in_year):
							yield v
			
			else: # for SECONDLY,MINUTELY,HOURLY,DAILY
				# limit
				for value in src:
					if weeks[value.weekday()] in part: # integer modifier is not permitted by specification.
						yield value
	
		def bymonthday(src, part):
			def resolve(value):
				days = part
				if len([p for p in part if p<0]):
					head = value.replace(day=1)
					end = (head + timedelta(40)).replace(day=1)
					ceil = (end - head).days + 1
					days = [p for p in days if p>0]+[ceil+p for p in part if p<0]
				return sorted(set([p for p in days if p>0])) # ignores -31 in some month
		
			if freq == "WEEKLY":
				pass # invalid by specification
			elif freq in ("MONTHLY", "YEARLY"):
				value = next(src)
				for p in resolve(value):
					if p >= value.day:
						yield value.replace(day=p)
			
				for value in src:
					for p in resolve(value):
						yield value.replace(day=p)
			else:
				for value in src:
					if value.day in resolve(value):
						yield value
	
		def byyearday(src, part):
			def resolve(value):
				ydays = part
				if len([p for p in part if p<0]):
					head = value.replace(month=1, day=1)
					end = (head + timedelta(400)).replace(month=1, day=1)
					ceil = (end - head).days + 1
					ydays = [p for p in ydays if p>0]+[ceil+p for p in part if p<0]
				return sorted(set([p for p in ydays if p>0])) # ignores -31 in some month
			
			def tm_resolve(value):
				head = value.replace(month=1, day=1)
				return [head+timedelta(p) for p in resolve(value)]
			
			if freq in ("DAILY", "WEEKLY", "MONTHLY"):
				pass
			elif freq == "YEARLY":
				# expand
				value = next(src)
				for p in tm_resolve(value):
					if p>=value:
						yield value
			
				for value in src:
					for p in tm_resolve(value):
						yield value
			else: # limit
				for value in src:
					if value.timetuple().yday in resolve(value):
						yield value
		
		def byweekno(src, part):
			weeks = weeks
			if freq != "YEARLY":
				return
			wkst = weeks.index(self.get("WKST", "MO").upper())
			part = sorted(part, key=lambda x:(x-wkst)%7)
			
			def expand(value):
				wday = value.weekday()
				ystart = value.replace(month=1, day=1)
				lead = (ystart.weekday() - wkst) % 7
				if len([p for p in part if p<0]):
					yend = (ystart + timedelta(400)).replace(month=1, day=1)
					tail = (yend.weekday() - wkst) % 7
					weeks = ((yend - ystart).days + lead) // 7
					if lead > 3:
						weeks -= 1
					if tail > 3:
						weeks += 1
					part = [p for p in part if p>0] + [weeks+p for p in part if p<0 and weeks+p>0]
				part = sorted(set(part))
			
				head = ystart + timedelta((wday - ystart.weekday()) % 7)
				if prelength < 3:
					# 1/1 is week #1
					if (wday - wkst) % 7 < lead:
						scans = [head + (p-2)*timedelta(weeks=1) for p in part if p > 1]
					else:
						scans = [head + (p-1)*timedelta(weeks=1) for p in part if p > 0]
				else:
					# 1/1 is week #0, which can't be specified.
					if (wday - wkst) % 7 < lead:
						scans = [head + (p-1)*timedelta(weeks=1) for p in part if p > 0]
					else:
						scans = [head + p*timedelta(weeks=1) for p in part if p > 0]
				return [u for u in scans if u.year==value.year]
		
			value = next(src)
			for v in expand(value):
				if v >= value:
					yield v
		
			for value in src:
				for v in expand(value):
					yield v
	
		def bymonth(src, part):
			if freq == "YEAR":
				part = sorted([p for p in part if 0<p<13])
				def expand(value):
					return [value.replace(month=p) for p in part]
			
				value = next(src)
				for v in expand(value):
					if v >= value:
						yield v
				
				for value in src:
					for v in expand(value):
						yield v
			else:
				for value in src:
					if value.month in part:
						yield value
		
		def repeat():
			if not dtstart:
				return
			
			cur = dtstart
			yield cur
			
			const_delta = dict(
				SECONDLY = timedelta(seconds=1),
				MINUTELY = timedelta(minutes=1),
				HOURLY = timedelta(hours=1),
				DAILY = timedelta(days=1),
				WEEKLY = timedelta(weeks=1),
			)
			interval = self.get("INTERVAL", 1)
			while freq:
				if freq in const_delta:
					cur = cur + const_delta[freq] * interval
				elif freq == "MONTHLY":
					for _ in range(interval):
						cur = (cur + timedelta(40)).replace(day=cur.day)
				elif freq == "YEARLY":
					for _ in range(interval):
						cur = (cur + timedelta(400)).replace(month=cur.month, day=cur.day)
				else:
					break
				
				context["setno"] += 1
				yield cur
		
		src = repeat()
		parts = "BYMONTH BYWEEKNO BYYEARDAY BYMONTHDAY BYDAY BYHOUR BYMINUTE BYSECOND BYSETPOS COUNT UNTIL".split()
		for part in parts:
			value = self.get(part)
			if value:
				src = locals()[part.lower()](src, value)
		
		try:
			for value in src:
				yield value
		except OverflowError as e:
			pass

@vtype("TEXT")
class Text(str_cls):
	pattern = re.compile(r"(\\[\\;,Nn])")
	build_pattern = re.compile(r"([\\;,\n])")
	escaping = (("\\\\","\\"),("\\;",";"),("\\,",","),("\\N","\n"),("\\n","\n"))
	
	@classmethod
	def parse(cls, value, tzinfo):
		esc = dict(cls.escaping)
		self = cls("".join([esc.get(tok, tok) for tok in cls.pattern.split(value)]))
		return self
	
	@classmethod
	def build(cls, self):
		esc = dict([(a,b) for b,a in cls.escaping])
		return "".join([esc.get(tok, tok) for tok in cls.build_pattern.split(self)])

@rich_eq
@vtype("TIME")
class Time(time):
	pattern = re.compile(r"^(\d{2})(\d{2})(\d{2})(Z?)$")
	leap = 0
	@classmethod
	def parse(cls, value, tzinfo):
		m = cls.pattern.match(value)
		if not m:
			raise ValueError("TIME format error")
		args = list(map(int, m.groups()[:3]))
		if not 0 <= args[0] <= 23:
			raise ValueError("TIME hour out of range")
		if not 0 <= args[1] <= 59:
			raise ValueError("TIME minute out of range")
		if not 0 <= args[2] <= 60:
			raise ValueError("TIME second out of range")
		
		leap = 0
		if args[2] == 60:
			leap = 1
			args[2] = 59
		
		if m.group(4): # Z
			tzinfo = utc
		
		self = time.__new__(cls, *args, tzinfo=tzinfo)
		self.leap = leap
		return self
	
	@classmethod
	def build(cls, self):
		arg = (self.hour, self.minute, self.second)
		if isinstance(self,DateTime) and self.leap:
			arg = (self.hour, self.minute, 60)
		return "%02d%02d%02d" % arg

@vtype("URI")
class Uri(str_cls):
	@classmethod
	def parse(cls, value, tzinfo):
		self = cls(value)
		return self
	
	@classmethod
	def build(cls, self):
		return self

@rich_eq
@vtype("UTC-OFFSET")
class UtcOffset(tzinfo):
	pattern = re.compile(r"^[+-](?P<hours>\d{2})(?P<minutes>\d{2})(?P<seconds>\d{2})?$")
	offset = timedelta(0)
	
	def utcoffset(self, d):
		return self.offset
	
	def dst(self, dt):
		return timedelta(0)
	
	def tzname(self, dt):
		if self.offset == timedelta(0):
			return "UTC"
		fmt = "UTC+%02d%02d"
		offset = self.offset
		if self.offset < timedelta(0):
			fmt = "UTC-%02d%02d"
			offset = -self.offset
		seconds = offset.seconds
		minutes = seconds//60
		if seconds % 60 == 0:
			return fmt % (minutes//60, minutes%60)
		else:
			return (fmt+".%02d") % (minutes//60, minutes%60, seconds%60)
	
	@classmethod
	def parse(cls, value, tzinfo):
		parts = cls.pattern.match(value)
		if parts is None:
			raise ValueError("UTC-OFFSET format error")
		
		delta_arg = {}
		for k,v in parts.groupdict().items():
			if v is None:
				continue
			delta_arg[k] = int(v)
		
		offset = timedelta(**delta_arg)
		self = cls()
		if value[0]=="-":
			self.offset = -offset
		else:
			self.offset = offset
		return self
	
	@classmethod
	def build(cls, self):
		fmt = "+%02d%02d"
		offset = self.utcoffset(datetime.now())
		if offset < timedelta():
			fmt = "-%02d%02d"
			offset = -offset
		
		seconds = offset.seconds
		minutes = seconds//60
		if seconds % 60 == 0:
			return fmt % (minutes//60, minutes%60)
		else:
			return (fmt+"%02d") % (minutes//60, minutes%60, seconds%60)

utc = UtcOffset.parse("+0000", None)

def comp_dtend(obj):
	for k in ("DURATION","DTEND","DUE"):
		v = obj.get(k)
		if v is None:
			continue
		return v

class vdatetime_cmp(object):
	def __init__(self, floating_tz = None):
		if floating_tz is None:
			floating_tz = utc
		self.ftz = floating_tz
	
	def __call__(self, a, b):
		def cmp(a,b): # for python3
			if a < b:
				return -1
			elif a==b:
				return 0
			else:
				return 1
		
		if isinstance(a, datetime):
			if isinstance(b, datetime):
				if a.tzinfo:
					if b.tzinfo:
						return cmp(a,b)
					else:
						return cmp(a,b.replace(tzinfo=self.ftz))
				elif b.tzinfo:
					return -self(b,a)
				else:
					return cmp(a,b)
			elif isinstance(b, date):
				return cmp(a.date(), b)
		elif isinstance(b, datetime):
			return -self(b,a)
		# noreach
		return cmp(a, b)

class Merger(object):
	def __init__(self, key=None):
		self.generators = []
		self.key = key
	
	def add(self, generator, *data):
		self.generators.append((generator, data))
	
	def __call__(self):
		cur = [[next(g), g, d] for g,d in self.generators]
		while len(cur):
			if self.key:
				cur = sorted(cur, key=lambda x:self.key(x[0]))
			else:
				cur = sorted(cur, key=lambda x:x[0])
			v,g,d = cur[0]
			yield tuple([v] + list(d))
			try:
				cur[0][0] = next(g)
			except StopIteration:
				cur = cur[1:]
