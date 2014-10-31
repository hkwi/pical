from datetime import datetime, date, time, timedelta, tzinfo
import re
import logging
digits = re.compile("^\d+$")

class uc(str):
	# case insensitive string (upper cased)
	def __hash__(self):
		return self.upper().__hash__()
	
	def __eq__(self, other):
		return self.upper() == other.upper()
	
	def __ne__(self, other):
		return self.upper() != other.upper()

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
		if len(nx) > 0 and nx[0] in (" ", "\t", b" ", b"\t"):
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
		m = re.match(r"^([a-zA-Z0-9-]+)([;:])", line)
		if not m:
			logger.error("contentline name error L%d" % lineno)
		name,nx = m.groups()
		line = line[len(m.group(0)):]
		params = []
		while nx==";":
			m = re.match(r'^([a-zA-Z0-9-]+)=([^\x00-\x1F\x7F"]*?|"[^\x00-\x1F\x7F";:,]*?")([,:;])', line)
			if not m:
				logger.error("contentline param error L%d" % lineno)
			pname,pval,nx = m.groups()
			line = line[len(m.group(0)):]
			vals=[pval]
			while nx == ",":
				m = re.match(r'^([^\x00-\x1F\x7F"]*?|"[^\x00-\x1F\x7F";:,]*?")([,:;])', line)
				if not m:
					logger.error("contentline multi param error L%d" % lineno)
				pval,nx = m.groups()
				line = line[len(m.group(0)):]
				vals.append(pval)
			params.append((uc(pname), vals))
		name = uc(name)
		value = line
		
		if name == "BEGIN":
			tzdb = comp.tzdb
			if tzdb is None:
				tzdb = {}
			
			sub = Component.factory(uc(value), tzdb)
			if params:
				logger.error("component takes no parameter L%d" % lineno)
			
			comp.children.append(sub)
			stack.append(comp)
			comp = sub
		elif name == "END":
			if comp.name == value:
				try:
					comp.verify()
				except Exception as e:
					logger.error("%s L%d" % (e,lineno))
				comp = stack.pop()
			else:
				logger.error("END does not match with BEGIN L%d" % lineno)
		else:
			try:
				comp.addProperty(name, value, params)
			except Exception as ex:
				logger.error("property %s value parse error: %s L%d" % (name,ex,lineno))
	
	if comp.name != " root":
		raise ValueError("missing END L%d" % lineno)
	return comp.children

class Component(object):
	defaultType = {
		"CALSCALE": "TEXT",
		"METHOD": "TEXT",
		"PRODID": "TEXT",
		"VERSION": "TEXT",
		"ATTACH": "URI",
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
		"DTEND": "DATE-TIME",
		"DUE": "DATE-TIME",
		"DTSTART": "DATE-TIME",
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
		"RECURRENCE-ID": "DATE-TIME",
		"RELATED-TO": "TEXT",
		"URL": "URI",
		"UID": "TEXT",
		"EXDATE": "DATE-TIME",
		"EXRULE": "RECUR",
		"RDATE": "DATE-TIME",
		"RRULE": "RECUR",
		"ACTION": "TEXT",
		"REPEAT": "INTEGER",
		"TRIGGER": "DURATION",
		"CREATED": "DATE-TIME",
		"DTSTAMP": "DATE-TIME",
		"LAST-MODIFIED": "DATE-TIME",
		"SEQUENCE": "INTEGER",
		"REQUEST-STATUS": "TEXT",
	}

	valueDelimiter = {
		"GEO": ";",
		"FREEBUSY": ",",
		"EXDATE": ",",
		"RDATE": ",",
		"REQUEST-STATUS": ";",
	}

	props = dict(
		VCALENDAR = dict(
			key = "PRODID VERSION",
			once = "CALSCALE METHOD",
			),
		VEVENT = dict(
			key = "DTSTAMP UID",
			once = "DTSTART"
				" CLASS CREATED DESCRIPTION GEO"
				" LAST-MODIFIED LOCATION ORGANIZER PRIORITY"
				" SEQUENCE STATUS SUMMARY TRANSP"
				" URL RECURRENCE-ID RESOURCES"
				" DTEND DURATION",
			many = "RRULE"
				" ATTACH ATTENDEE CATEGORIES COMMENT"
				" CONTACT EXDATE REQUEST-STATUS RELATED-TO"
				" RDATE",
			),
		VTODO = dict(
			key = "DTSTAMP UID",
			once = "CLASS COMPLETED CREATED DESCRIPTION"
				" DTSTART GEO LAST-MODIFIED LOCATION ORGANIZER"
				" PERCENT-COMPLETE PRIORITY RECURRENCE-ID SEQUENCE STATUS"
				" SUMMARY URL"
				" DUE DURATION",
			many = "RRULE"
				" ATTACH ATTENDEE CATEGORIES COMMENT CONTACT"
				" EXDATE REQUEST-STATUS RELATED-TO RESOURCES"
				" RDATE",
			),
		VJOURNAL =dict(
			key = "DTSTAMP UID",
			once = "CLASS CREATED DTSTART"
				" LAST-MODIFIED ORGANIZER RECURRENCE-ID SEQUENCE"
				" STATUS SUMMARY URL",
			many = "RRULE"
				" ATTACH ATTENDEE CATEGORIES COMMENT"
				" CONTACT DESCRIPTION EXDATE RELATED-TO RDATE"
				" REQUEST-STATUS",
			),
		VFREEBUSY = dict(
			key = "DTSTAMP UID",
			once = "CONTACT DTSTART DTEND"
				" ORGANIZER URL",
			many = "ATTENDEE COMMENT FREEBUSY REQUEST-STATUS",
			),
		VTIMEZONE = dict(
			key = "TZID",
			once = "LAST-MODIFIED TZURL",
			),
		DAYLIGHT = dict(
			once = "DTSTART TZOFFSETTO TZOFFSETFROM",
			many = "RRULE"
				" COMMENT RDATE TZNAME",
			),
		STANDARD = dict(
			once = "DTSTART TZOFFSETTO TZOFFSETFROM",
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
		self.name = uc(name)
		self.tzdb = tzdb
		self.children = []
		self.properties = []
	
	def __getitem__(self, name):
		for prop in self.properties:
			if prop[0] == name:
				return prop[1]
		raise KeyError("property %s not found" % name)
	
	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default
	
	def list(self, name):
		return [prop[1] for prop in self.properties if prop[0] == name]
	
	def verify(self):
		info = self.props.get(self.name, {})
		for constraint,props in info.items():
			for prop in props.split():
				if constraint == "key":
					assert len(self.list(prop))==1, "component %s requires property %s" % (self.name, prop)
				elif constraint == "once":
					assert len(self.list(prop))<2, "component %s optional property %s must not occur more than once in %s" % (self.name, prop)
		
		for name,value,params in self.properties:
			if name in self.defaultType:
				accept = False
				for constraint,props in info.items():
					if name in props.split():
						accept = True
				if not accept:
					raise ValueError("property %s is not defined in component %s" % (name, self.name))
		
		if self.name in "VEVENT VTODO VJOURNAL DAYLIGHT STANDARD".split():
			for name in ("RRULE","EXRULE"):
				recurrs = self.list(name)
				if len(recurrs) > 1:
					logger.warn("property RRULE should not occur more than once")
				for recur in recurrs:
					assert recur.get("FREQ"), "FREQ part is required in property %s" % name
		
		if self.name == "VEVENT":
			if self.get("DTEND") and self.get("DURATION"):
				raise ValueError("either DTEND or DURATION may appear")
		elif self.name == "VTODO":
			if self.get("DUE") and self.get("DURATION"):
				raise ValueError("either DUE or DURATION may appear")
		elif self.name == "VALARM":
			duration = self.get("DURATION")
			repeat = self.get("REPEAT")
			if (duration is None and repeat is not None) or (duration is not None and repeat is None):
				raise ValueError("both DURATION and REPEAT must occur")
		
		if self.name == "VEVENT":
			dtstart_list = self.list("DTSTART")
			if self.get("METHOD") is None:
				assert len(dtstart_list)==1, "DTSTART is REQUIRED"
			assert len(dtstart_list) < 2, "DTSTART must not occur more than once"
			dtstart = dtstart_list[0]
			if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
				dtend = self.get("DTEND")
				if dtend:
					assert isinstance(dtend, date) and not isinstance(dtend, datetime), "DTEND must be DATE value also"
				dur = self.get("DURATION")
				if dur:
					assert dur.seconds == 0, "DATE DTSTART may have only dur-day or dur-week DURATION"
		elif self.name == "VTIMEZONE":
			self.tzdb[self["TZID"]] = self
		elif self.name in ("DAYLIGHT", "STANDARD"):
			assert self["DTSTART"].tzinfo is None, "DTSTART in %s is local DATE-TIME value" % self.name
			for rdate in self.list("RDATE"):
				for r in rdate:
					if isinstance(r, Period):
						r = r[0]
					assert isinstance(r, datetime) and r.tzinfo is None, "RDATE in %s is local date with local time" % self.name
		elif self.name == "VALARM":
			action = self.get("ACTION")
			if action=="AUDIO":
				assert len(self.list("ATTACH")) < 2, "AUDIO VALARM may include one ATTACH property"
			elif action=="DISPLAY":
				assert len(self.list("DESCRIPTION")), "DISPLAY VALARM must include DESCRIPTION"
			elif action=="EMAIL":
				assert len(self.list("DESCRIPTION")), "EMAIL VALARM must include DESCRIPTION"
				assert len(self.list("SUMMARY")), "EMAIL VALARM must include SUMMARY"
				assert len(self.list("ATTENDEE"))>0, "EMAIL VALARM must include ATTENDEE"
		elif self.name == "VCALENDAR":
			for comp in self.children:
				recurid = comp.get("RECURRENCE-ID")
				if recurid is None:
					continue
				for c in self.children:
					if len(c.list("RECURRENCE-ID"))==0 and c.name==comp.name and c["UID"]==comp["UID"]:
						assert type(c["DTSTART"])==type(recurid), "RECURRENCE-ID type must be same with reference DTSTART type"
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
	
	def dtend(self):
		return self.get("DURATION",
			self.get("DTEND",
			self.get("DUE")))
	
	def addProperty(self, name, value, params):
		if self.name == " root":
			raise ValueError("no component to add to")
		
		pdic = dict(params)
		tzinfo = self.pickTzinfo(pdic.get("TZID",[None])[0])
		vtype = _vtype.get(pdic.get("VALUE", [self.defaultType.get(name)])[0], Text)
		delim = self.valueDelimiter.get(name)
		if delim:
			value = [vtype.parse(v, tzinfo) for v in value.split(delim)]
		else:
			value = vtype.parse(value, tzinfo)
		
		self.properties.append((name, value, params))
	
	def serialize(self):
		yield "BEGIN:%s" % self.name
		
		def tzhook(base,value,params):
			if value.tzinfo is not None:
				if value.tzinfo == utc or value.tzinfo.tzname(datetime.now()) == "UTC":
					base += "Z"
				elif dict(params).get("TZID") is None:
					if isinstance(value.tzinfo, Timezone):
						params.append(("TZID", value["TZID"]))
					else:
						params.append(("TZID", "/"+str(value)))
			return base,params
		
		for name,value,params in self.properties:
			klass = vtype_resolve(value)
			if klass:
				vstr = klass.build(value)
				if klass in (DateTime, Time):
					vstr,params = tzhook(vstr,value,params)
			else:
				vstr = repr(value)
			
			yield "%s%s:%s" % (name, "".join([";%s=%s" % (k,",".join(v)) for k,v in params]), vstr)
		for c in self.children:
			for s in c.serialize():
				yield s
		yield "END:%s" % self.name
	
	def clone(self):
		# component is mutable, properties are immutable
		exp = self.factory(self.name, self.tzdb)
		exp.children = [c.clone() for c in self.children]
		exp.properties += self.properties
		return exp
	
	@classmethod
	def factory(cls, name, tzdb):
		if name == "VCALENDAR":
			self = Calendar(name, tzdb)
		elif name == "VTIMEZONE":
			self = Timezone(name, tzdb)
		else:
			self = cls(name, tzdb)
		return self

class Calendar(Component):
	def time_range(self, start=None, end=None, floating_tz=None, component=None, expand=False):
		# caldav time-range query
		assert start or end, "start or end must be specified"
		if start and end:
			assert start < end, "end must be greater than start"
		for dt in (start,end):
			if dt:
				assert isinstance(dt,datetime) and dt.tzinfo, "start, end must be a datetime in UTC"
		if expand:
			assert end, "expansion requires end"
		
		dtcmp = vdatetime_cmp(floating_tz)
		def vevent_overlap(dtstart, dtend, obj):
			ret = True
			if dtend:
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
				ret &= dtcmp(start, dtstart) <= 0
				ret &= dtcmp(end, dtstart) > 0
			else:
				ret &= dtcmp(start, dtstart+timedelta(1)) < 0
				ret &= dtcmp(end, dtstart) > 0
			return ret
		
		def vtodo_overlap(dtstart, dtend, obj):
			ret = True
			if dtstart:
				if dtend:
					if isinstance(dtend, timedelta): # DURATION
						ret &= dtcmp(strt,dtstart+dtend)<=0
						if end:
							ret &= dtcmp(end>dtstart) or dtcmp(end,dtstart+dtend)>=0
					else:
						ret &= dtcmp(start,dtend)<0 or dtcmp(start,dtstart)<=0
						if end:
							ret &= dtcmp(end,dtstart)>0 or dtcmp(end,dtend)>=0
				else:
					ret &= dtcmp(start,dtstart)<=0
					if end:
						ret &= dtcmp(end,dtstart)>0
			else:
				completed = obj.get("COMPLETED")
				created = obj.get("CREATED")
				if completed:
					if created:
						ret &= dtcmp(start,created)<=0 or dtcmp(start,completed)<=0
						if end:
							ret &= dtcmp(end,created)>=0 or dtcmp(end,completed)>=0
					else:
						ret &= dtcmp(start,completed)<=0
						if end:
							ret &= dtcmp(end,completed)>=0
				elif created:
					if end:
						ret &= end > created
			return ret
		
		def vjournal_overlap(dtstart, dtend, obj):
			ret = True
			if dtstart:
				if isinstance(dtstart,datetime):
					ret &= dtcmp(start,dtstart)<=0
				else:
					ret &= dtcmp(start,dtstart+timedelta(1))<0
				if end:
					ret &= dtcmp(end,dtstart)>0
			else:
				ret = False
			return ret
		
		def vfreebusy_overlap(dtstart, dtend, obj):
			ret = True
			freebusy = obj.get("FREEBUSY")
			if dtstart and dtend:
				ret &= dtcmp(start,dtend)<=0
				if end:
					ret &= dtcmp(end,dtstart)>0
			elif freebusy:
				ret &= dtcmp(start,freebusy[1])<0
				ret &= dtcmp(end,freebusy[0])>0
			else:
				ret = False
			
			return ret
		
		def valarm_overlap(dtstart, dtend, obj):
			# dtstart, dtend is the container's value
			for name,value,params in obj.properties:
				if name!="TRIGGER":
					continue
				
				if isinstance(value, timedelta):
					rel = dict(params).get("RELATED",[""])[0]
					if rel == "START":
						trigger_time = dtstart - value
					elif rel == "END":
						if isinstance(dtend, timedelta):
							trigger_time = dtstart + dtend - value
						else:
							trigger_time = dtend - value
				else:
					trigger_time = value
				
				duration = obj.get("DURATION")
				for count in range(obj.get("REPEAT",0)+1):
					dt = trigger_time + duration*count
					ret = dtcmp(start, dt)<=0
					if end:
						ret &= dtcmp(end, dt)>0
					if ret:
						return True
			return False
		
		overlaps = dict(
			VEVENT = vevent_overlap,
			VTODO = vtodo_overlap,
			VJOURNAL = vjournal_overlap,
			VFREEBUSY = vfreebusy_overlap,
			VALARM = valarm_overlap,
		)
		
		def expanded(dtstart,dtend,base,upon):
			def value_param(name, value, params):
				vname = None
				tname = self.defaultType[name]
				if tname != "TEXT":
					klass = vtype_resolve(value)
					if klass != _vtype[tname]:
						for k,v in _vtype.items():
							if v == klass:
								vname = k
				params = [param for param in params if param[0]!="VALUE"]
				if vname:
					params.append(("VALUE",[vname]))
				return params
			
			if upon:
				exp = upon.clone()
				if exp.dtend() is None and dtend:
					if isinstance(dtend,timedelta):
						name = "DURATION"
					elif cname == "VTODO":
						name = "DUE"
					else:
						name = "DTEND"
					
					exp.properties.append((name,dtend,value_param(name,dtend,[])))
				
				for name,value,params in base.properties:
					if name in ("RRULE","EXRULE","RDATE","EXDATE"):
						continue
					if name in ("DURATION","DTEND","DUE") and exp.dtend():
						continue
					
					if name in ("DUE","DTEND"):
						exp.properties.append((name, exp["DTSTART"]+(base[name]-base["DTSTART"]), params))
					elif name in self.props[cname]["once"] and len(exp.list(name))==0:
						exp.properties.append((name,value,params))
					elif name in self.props[cname]["key"] and len(exp.list(name))==0:
						exp.properties.append((name,value,params))
					else:
						exp.properties.append((name,value,params))
				
				exp.properties.append(("RECURRENCE-ID",dtstart,value_param("RECURRENCE-ID", dtstart,[])))
			elif dtstart == base["DTSTART"] and not expand:
				exp = base
			else:
				exp = base.clone()
				exp.properties = [("DTSTART", dtstart, value_param("DTSTART", dtstart, []))]
				for name,value,params in base.properties:
					if name in ("DTSTART", "RRULE", "RDATE", "EXDATE", "EXRULE"):
						continue
					elif name in ("DURATION","DTEND","DUE"):
						if dtend is None:
							if isinstance(value,timedelta):
								dtend = value
							else:
								dtend = dtstart+(value-base["DTSTART"])
						
						if isinstance(dtend,timedelta):
							name = "DURATION"
						elif cname == "VTODO":
							name = "DUE"
						else:
							name = "DTEND"
						
						exp.properties.append((name,dtend,value_param(name, dtend, [])))
					else:
						exp.properties.append((name,value,params))
				
				exp.properties.append(
					("RECURRENCE-ID", dtstart, value_param("RECURRENCE-ID", dtstart, []))
					)
			return exp
		
		found = set()
		found_ordered = []
		for cname in "VEVENT VTODO VJOURNAL VFREEBUSY".split():
			if component is not None and component != "VALARM" and component != cname:
				continue
			
			uids = set([c.get("UID") for c in self.children if c.name==cname])
			if end is None:
				for c in self.children:
					if cname != c.name:
						continue
					ulim_rrule = sorted([sorted(recurr.items()) for recurr in c.list("RRULE")
						if recurr.get("UNTIL") is None and recurr.get("COUNT") is None])
					ulim_erule = sorted([sorted(recurr.items()) for recurr in c.list("EXRULE")
						if recurr.get("UNTIL") is None and recurr.get("COUNT") is None])
					
					if ulim_rrule and ulim_rrule!=ulim_erule:
						uid = c.get("UID")
						uids.remove(uid)
						found.add(c)
						for c in self.children:
							if c.get("RECURRENCE-ID") is None or cname!=c.name or c["UID"]!=uid:
								continue
							
							exp = None
							if c.dtend() is None:
								wait1 = False
								for dtstart,dtend,base,upon in self.scan_uid(cname, uid, floating_tz, end):
									if upon == c:
										exp = expanded(dtstart,dtend,base,upon)
									if wait1:
										break
									if dtstart > c["DTSTART"]:
										wait1 = True
							else:
								exp = c
							
							if exp is None:
								logging.getLogger("pical").error("failed to resolve dtend(or duration) of a component with RECURRENCE-ID, ignoring")
								continue
							
							if overlaps[cname](exp["DTSTART"], exp.dtend(), exp):
								found.add(c)
			for uid in uids:
				for dtstart,dtend,base,upon in self.scan_uid(cname, uid, floating_tz, end):
					exp = expanded(dtstart,dtend,base,upon)
					dtstart = exp.get("DTSTART")
					dtend = exp.dtend()
					
					if (component is None or component == "VALARM") and cname in ("VEVENT","VTODO"):
						children = base.children
						if upon:
							children += upon.children
						for c in children:
							if c.name != "VALARM":
								continue
							
							if overlaps["VALARM"](dtstart, dtend, c):
								if expand:
									found_ordered.append(exp)
								else:
									found.add(base)
									if upon:
										found.add(upon)
					
					if component is None or component == cname:
						if overlaps[cname](dtstart, dtend, exp):
							if expand:
								found_ordered.append(exp)
							else:
								found.add(base)
								if upon:
									found.add(upon)
		cal = Calendar(self.name, self.tzdb)
		cal.children = [c for c in self.children if c.name=="VTIMEZONE"]
		if expand:
			cal.children += found_ordered
		else:
			cal.children += list(found)
		
		cal.properties += self.properties
		return cal
	
	def scan(self, component_name, floating_tz=None, end=None):
		# yields (onset_dtstart, duration_or_dtend?, generator_component, modifier_component?)
		uids = set()
		for c in self.children:
			if c.name != component_name:
				continue
			uids.add(c["UID"])
		
		merger = Merger(cmp=lambda x,y:vdatetime_cmp(floating_tz)(x[0],y[0]))
		for uid in uids:
			merger.add(self.scan_uid(component_name, uid, end=None))
		
		for m in merger():
			yield m[0]
	
	def scan_uid(self, component_name, uid, floating_tz=None, end=None):
		# yields (onset_dtstart, duration_or_dtend?, generator_component, modifier_component?)
		rbases = []
		rmods = []
		for c in self.children:
			if c.name == component_name and c["UID"]==uid:
				if len(c.list("RECURRENCE-ID"))==0:
					rbases.append(c)
				else:
					rmods.append(c)
		
		if not rbases: # already expanded
			for r in sorted(rmods, cmp=self.sorter[component_name]):
				yield r.get("DTSTART"), None, r, None
		
		# yields (onset_dtstart, duration_or_dtend?, generator_component, modifier_component?)
		combined = Merger(cmp=lambda x,y:vdatetime_cmp(floating_tz)(x[0],y[0]))
		for rbase in rbases:
			# yields (onset_dtstart, duration_or_dtend?)
			setter = Merger(cmp=lambda x,y:vdatetime_cmp(floating_tz)(x[0],y[0]))
			unsetter = Merger(cmp=lambda x,y:vdatetime_cmp(floating_tz)(x[0],y[0]))
			
			for key,m in (("RDATE", setter), ("EXDATE", unsetter)):
				for values in rbase.list(key):
					dates = []
					for value in values:
						if isinstance(value, Period):
							dates.append(value)
						else:
							dates.append((value, None))
					
					m.add(iter(dates), rbase)
			
			dtstart = rbase["DTSTART"]
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
					(udset,_),_ = unsetter.next()
				except StopIteration:
					unset = None
				
				for (dtstart,dtend),rbase in setter:
					if unset is not None:
						while unset < dtstart:
							try:
								(unset,_),_ = unsetter.next()
							except StopIteration:
								unset = None
								break
					
					if unset is None or dtstart != unset:
						yield dtstart,dtend,rbase
			
			# put in running status
			combined.add(filtered(setter(), unsetter()))
		
		combined = combined()
		for (dtstart, dtend, rbase), in combined:
			if end and vdatetime_cmp(floating_tz)(dtstart,end) >0:
				break
			
			def lookup_modifier(dttest):
				for rmod in rmods:
					for name,value,params in rmod.properties:
						if name == "RECURRENCE-ID":
							if dict(params).get("RANGE")=="THISANDFUTURE":
								if dttest >= value:
									return rmod
							else:
								if dttest == value:
									return rmod
				return None
			
			yield dtstart, dtend, rbase, lookup_modifier(dtstart)

class Timezone(tzinfo, Component):
	def utcoffset(self, dt):
		comp = self.scan(dt)
		if comp:
			return comp["TZOFFSETTO"].utcoffset(dt)
		else:
			return timedelta(0)
	
	def dst(self, dt):
		comp = self.scan(dt)
		if comp and comp.name == "DAYLIGHT":
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
			if c.name not in ("DAYLIGHT", "STANDARD"):
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


## Property Value Data Types
_vtype = {}
def vtype(name):
	def register(klass):
		_vtype[uc(name)] = klass
		return klass
	return register

def vtype_resolve(value):
	if value is True or value is False:
		return Boolean
	elif isinstance(value, tuple(_vtype.values())):
		return value.__class__
	elif isinstance(value,str):
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
		v = uc(value)
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
class CalAddress(str):
	@classmethod
	def parse(cls, value, tzinfo):
		self = cls(value)
		return self
	
	@classmethod
	def build(cls, self):
		return self

@vtype("DATE")
class Date(date):
	pattern = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
	@classmethod
	def parse(cls, value, tzinfo):
		m = cls.pattern.match(value)
		if not m:
			raise TypeError("DATE value format error")
		year,month,mday = map(int, m.groups())
		self = date.__new__(cls, year, month, mday)
		return self
	
	@classmethod
	def build(cls, self):
		return "%04d%02d%02d" % (self.year, self.month, self.day)

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
		return self.strftime("%Y%m%dT%H%M%S")


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
		if self < 0:
			parts.append("-")
			self = -self
		if self.days%7==0:
			parts.append("%dW" % self.days//7)
		else:
			parts.append("%dD" % self.days)
		if self.seconds > 0:
			parts.append("T")
			if self.seconds//3600:
				parts.append("%dH" % self.seconds//3600)
			if (self.seconds//60)%60:
				parts.append("%dM" % (self.seconds//60)%60)
			if self.seconds%60:
				parts.append("%dS" % self.seconds%60)
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

@vtype("RECUR")
class Recur(object):
	freq = ("SECONDLY", "MINUTELY", "HOURLY", "DAILY", "WEEKLY", "MONTHLY", "YEARLY")
	weekday = "MO TU WE TH FR SA SU".split()
	ranges = dict(
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
		for item in self._items:
			if item[0] == key:
				return item[1]
		raise KeyError("Parameter %s not found" % key)
	
	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default
	
	@classmethod
	def parse(cls, value, tzinfo):
		items = []
		for k,v in [kv.split("=") for kv in value.split(";")]:
			k = uc(k)
			if k == "freq":
				if v not in cls.freq:
					raise ValueError("FREQ parameter value error")
				items.append((k,v))
			elif k in ("count","interval"):
				items.append((k,int(v)))
			elif k in cls.ranges:
				items.append((k,map(digits(*cls.ranges[k]), v.split(","))))
			elif k == "UNTIL":
				try:
					items.append((k,Date.parse(v, tzinfo)))
				except:
					items.append((k,DateTime.parse(v, tzinfo)))
			elif k == "BYDAY":
				values = v.split(",")
				map(digits(True,1,366), [v[:-2] for v in values if len(v)!=2])
				for v in values:
					if v[-2:] not in cls.weekday:
						raise ValueError("BYDAY parameter error")
				items.append((k,values))
			elif k == "WKST":
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
			if k=="FREQ":
				part.append(v)
			elif k in ("COUNT","INTERVAL"):
				part.append("%d" % v)
			elif k in cls.ranges:
				part.append(",".join(["%d" % s for s in v]))
			elif k == "UNTIL":
				if isinstance(v,datetime):
					v = DateTime.build(v)
				else:
					v = Date.build(v)
				part.append(v)
			elif k in ("BYDAY", "WKST"):
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
				yield src.next()
	
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
			freq = uc(self.get("FREQ", ""))
			if freq == "SECONDLY":
				while True:
					value = src.next()
					if value.second in part:
						yield value
					# XXX: add leap time support
			else:
				# datetime module does not support leap time
				nonleap = set([p for p in part if 0<=p<=59])
				if 60 in part:
					nonleap.add(59)
				
				part = sorted(nonleap)
				value = src.next()
				for p in part:
					if p >= value.second:
						yield value.replace(second=p)
				
				for value in src:
					for p in part:
						yield value.replace(second=p)
	
		def byminute(src, part):
			freq = uc(self.get("FREQ", ""))
			if freq in ("SECONDLY", "MINUTELY"):
				for value in src:
					if value.minute in part:
						yield value
			else:
				part = sorted(set([p for p in part if 0<=p<=59]))
				value = src.next()
				for p in part:
					if p >= value.minute:
						yield value.replace(minute=p)
			
				for value in src:
					for p in part:
						yield value.replace(minute=p)
	
		def byhour(src, part):
			freq = uc(self.get("FREQ", ""))
			if freq in ("SECONDLY","MINUTELY","HOURLY"):
				for value in src:
					if value.hour in part:
						yield value
			else:
				part = sorted(set([p for p in part if 0<=p<=23]))
				value = src.next()
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
				
				cur = start + timedelta(days=(weekday - start.weekday())%7)
				scans = [cur + timedelta(weeks=1)*N for N in range(base)]
				return [s for s in scans if limit(s)]
		
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
			
			freq = uc(self.get("FREQ", ""))
			if freq == "WEEKLY":
				wkst = weeks.index(self.get("WKST", "MO"))
				part = sorted([(weeks.index(p)-wkst)%7 for p in part if len(p)==2])
				
				value = src.next()
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
					value = src.next()
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
					value = src.next()
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
		
			freq = uc(self.get("FREQ", ""))
			if freq == "WEEKLY":
				pass # invalid by specification
			elif freq in ("MONTHLY", "YEARLY"):
				value = src.next()
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
		
			freq = uc(self.get("FREQ", ""))
			if freq in ("DAILY", "WEEKLY", "MONTHLY"):
				pass
			elif freq == "YEARLY":
				# expand
				value = src.next()
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
			freq = uc(self.get("FREQ", ""))
			if freq != "YEARLY":
				return
			wkst = weeks.index(self.get("WKST", "MO"))
			part = sorted(part, cmp=lambda x,y: (x-wkst)%7 - (y-wkst)%7)
		
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
		
			value = src.next()
			for v in expand(value):
				if v >= value:
					yield v
		
			for value in src:
				for v in expand(value):
					yield v
	
		def bymonth(src, part):
			freq = uc(self.get("FREQ", ""))
			if freq == "YEAR":
				part = sorted([p for p in part if 0<p<13])
				def expand(value):
					return [value.replace(month=p) for p in part]
			
				value = src.next()
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
			freq = uc(self.get("FREQ", ""))
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
		
		for value in src:
			yield value

@vtype("TEXT")
class Text(str):
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

@vtype("TIME")
class Time(time):
	pattern = re.compile(r"^(\d{2})(\d{2})(\d{2})(Z?)$")
	leap = 0
	@classmethod
	def parse(cls, value, tzinfo):
		m = cls.pattern.match(value)
		if not m:
			raise ValueError("TIME format error")
		args = map(int, m.groups()[:3])
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
		return "%02d%02d%02d" % (self.hour, self.minute, self.second)

@vtype("URI")
class Uri(str):
	@classmethod
	def parse(cls, value, tzinfo):
		self = cls(value)
		return self
	
	@classmethod
	def build(cls, self):
		return self

@vtype("UTC-OFFSET")
class UtcOffset(tzinfo):
	offset = 0
	def utcoffset(self, d):
		return timedelta(minutes=self.offset)
	
	def dst(self, dt):
		return timedelta(0)
	
	def tzname(self, dt):
		if offset == 0:
			return "UTC"
		offset = abs(self.offset)
		fmt = "UTC+%02d%02d"
		if self.offset < 0:
			fmt = "UTC-%02d%02d"
		return fmt % (offset//60, offset%60)
	
	@classmethod
	def parse(cls, value, tzinfo):
		if len(value)!=5:
			raise ValueError("UTC-OFFSET format error")
		offset = int(value[1:3])*60 + int(value[3:5])
		if value[0]=="-":
			offset = -offset
		elif value[0]!="+":
			raise ValueError("UTF-OFFSET starts with sign")
		
		self = cls()
		self.offset = offset
		return self
	
	@classmethod
	def build(cls, self):
		fmt = "+%02d%02d"
		offset = self.utcoffset(datetime.now())
		if offset < timedelta():
			fmt = "-%02d%02d"
			offset = -offset
		return fmt % (offset.seconds//3600, (offset.seconds%3600)//60)

utc = UtcOffset.parse("+0000", None)

class vdatetime_cmp(object):
	def __init__(self, floating_tz = None):
		if floating_tz is None:
			floating_tz = utc
		self.ftz = floating_tz
	
	def __call__(self, a, b):
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
	def __init__(self, key=None, cmp=None):
		self.generators = []
		self.key = key
		self.cmp = cmp
	
	def add(self, generator, *data):
		self.generators.append((generator, data))
	
	def __call__(self):
		cur = [[g.next(), g, d] for g,d in self.generators]
		while len(cur):
			if self.cmp:
				cur = sorted(cur, cmp=lambda x,y:self.cmp(x[0],y[0]))
			elif self.key:
				cur = sorted(cur, key=lambda x:self.key(x[0]))
			else:
				cur = sorted(cur, key=lambda x:x[0])
			v,g,d = cur[0]
			yield tuple([v] + list(d))
			try:
				cur[0][0] = g.next()
			except StopIteration:
				cur = cur[1:]

