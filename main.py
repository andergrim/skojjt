﻿# -*- coding: utf-8 -*-
from data import *
from dataimport import *
import datetime
import urllib
import json
import scoutnet
import htmlform
from dakdata import *
from gaesessions import get_current_session, delete_expired_sessions
from google.appengine.api import users
from google.appengine.api import app_identity
from google.appengine.api import mail
import random
import os

from flask import Flask, render_template, abort, redirect, url_for, request, make_response
from werkzeug import secure_filename
import sys

app = Flask(__name__)
app.debug = True

# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

reload(sys)
sys.setdefaultencoding('utf8')

if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
	env = 'production'
else:
	env = 'local'


@app.route('/')
def home():
	breadcrumbs = [{'link':'/', 'text':'Hem'}]
	user = UserPrefs.current()
	session = get_current_session()
	user.attemptAutoGroupAccess()
	starturl = '/start/'
	personsurl = '/persons/'
	logouturl = users.create_logout_url('/')

	if user.groupaccess != None:
		starturl += user.groupaccess.urlsafe() + '/'
		personsurl += user.groupaccess.urlsafe() + '/'
	
	return render_template('start.html',
						   heading = 'Hem',
						   items = [],
						   breadcrumbs = breadcrumbs,
						   user = user,
						   starturl = starturl,
						   personsurl = personsurl,
						   logouturl = logouturl,
						   env = env,
						   session = session)

@app.route('/start')
@app.route('/start/')
@app.route('/start/<sgroup_url>')
@app.route('/start/<sgroup_url>/')
@app.route('/start/<sgroup_url>/<troop_url>', methods = ['POST', 'GET'])
@app.route('/start/<sgroup_url>/<troop_url>/', methods = ['POST', 'GET'])
@app.route('/start/<sgroup_url>/<troop_url>/<key_url>', methods = ['POST', 'GET'])
@app.route('/start/<sgroup_url>/<troop_url>/<key_url>/', methods = ['POST', 'GET'])
def start(sgroup_url=None, troop_url=None, key_url=None):
	user = UserPrefs.current()
	if not user.hasAccess():
		return "denied", 403
	
	session = get_current_session()
	breadcrumbs = [{'link':'/', 'text':'Hem'}]
	section_title = u'Kårer'
	breadcrumbs.append({'link':'/start', 'text':section_title})
	baselink='/start/'

	scoutgroup = None
	if sgroup_url != None:
		sgroup_key = ndb.Key(urlsafe=sgroup_url)
		scoutgroup = sgroup_key.get()
		baselink += sgroup_url+"/"
		breadcrumbs.append({'link':baselink, 'text':scoutgroup.getname()})

	troop = None
	if troop_url != None:
		baselink += troop_url+"/"
		troop_key = ndb.Key(urlsafe=troop_url)
		troop = troop_key.get()
		breadcrumbs.append({'link':baselink, 'text':troop.getname()})
		
	if key_url == "settings":
		section_title = u'Inställningar'
		baselink += "settings/"
		breadcrumbs.append({'link':baselink, 'text':section_title})
		if request.method == "POST":
			troop.defaultstarttime = request.form['defaultstarttime']
			troop.defaultduration = int(request.form['defaultduration'])
			troop.rapportID = int(request.form['rapportID'])
			troop.put()
			
		form = htmlform.HtmlForm('troopsettings')
		form.AddField('defaultstarttime', troop.defaultstarttime, 'Avdelningens vanliga starttid')
		form.AddField('defaultduration', troop.defaultduration, u'Avdelningens vanliga mötestid i minuter', 'number')
		form.AddField('rapportID', troop.rapportID, 'Unik rapport ID för kommunens närvarorapport', 'number')
		
		return render_template('form.html',
			heading = section_title,
			baselink = baselink,
			form = str(form),
			breadcrumbs = breadcrumbs,
			env = env,
			session = session)

	if key_url == "delete":
		if troop == None:
			return "", 404
		if len(request.form) > 0 and "confirm" in request.form:
			if not user.isGroupAdmin():
				return "", 403
			troop.delete()
			troop = None	
			del breadcrumbs[-1]
			baselink=breadcrumbs[-1]["link"]
		else:
			form = htmlform.HtmlForm('deletetroop', submittext="Radera", buttonType="btn-danger", 
				descriptionText = u"Vill du verkligen radera avdelningen och all registrerad närvaro?\nDet går här inte att ångra.")
			form.AddField('confirm', '', '', 'hidden')
			
			return render_template('form.html',
				heading = section_title,
				baselink = baselink,
				form = str(form),
				breadcrumbs = breadcrumbs,
				env = env,
				session = session)

	if key_url == "newperson":
		section_title = "Ny person"
		baselink += key_url + "/"
		breadcrumbs.append({'link':baselink, 'text':section_title})
		
		if request.method == "GET":
			return render_template('person.html',
				heading = section_title,
				baselink = baselink,
				breadcrumbs = breadcrumbs,
				trooppersons = [],
				scoutgroup = scoutgroup,
				env = env, 
				session = session)
		elif request.method == "POST":
			pnr = request.form['personnummer'].replace('-','')
			person = Person.createlocal(
				request.form['firstname'], 
				request.form['lastname'], 
				pnr, 
				Person.getIsFemale(pnr),
				request.form['mobile'],
				request.form['phone'],
				request.form['email'])
			person.street = request.form["street"]
			person.zip_code = request.form["zip_code"]
			person.zip_name = request.form["zip_name"]
			person.scoutgroup = sgroup_key
			logging.info("created local person %s", person.getname())
			person.put()
			troopperson = TroopPerson.create(troop_key, person.key, False)
			troopperson.commit()
			if scoutgroup.canAddToWaitinglist():
				if scoutnet.AddPersonToWaitinglist(
						scoutgroup,
						person.firstname,
						person.lastname,
						person.personnr,
						person.email,
						person.street,
						person.zip_code,
						person.zip_name,
						person.mobile,
						person.phone,
						troop):
					person.notInScoutnet = False
					person.put()
			return redirect(breadcrumbs[-2]['link'])
	
	if request.method == "GET" and len(request.args) > 0 and "action" in request.args:
		action = request.args["action"]
		logging.debug("action %s", action)
		if action == "lookupperson":
			if scoutgroup == None:
				raise ValueError('Missing group')
			name = request.args['name'].lower()
			if len(name) < 2:
				return "[]"
			logging.debug("name=%s", name)
			jsonstr='['
			personCounter = 0
			for person in Person().query(Person.scoutgroup == sgroup_key):
				if person.getname().lower().find(name) != -1 and not person.removed:
					if personCounter != 0:
						jsonstr += ', '
					jsonstr += '{"name": "'+person.getname()+'", "url": "' + person.key.urlsafe() + '"}'
					personCounter += 1
					if personCounter == 8:
						break
			jsonstr+=']'
			return jsonstr
		elif action == "addperson":
			if troop == None or key_url == None:
				raise ValueError('Missing troop or person')
			person_key = ndb.Key(urlsafe=key_url)
			person = person_key.get()
			logging.info("adding person=%s to troop=%s", person.getname(), troop.getname())
			troopperson = TroopPerson.create(troop_key, person_key, person.isLeader())
			troopperson.commit()
			return redirect(breadcrumbs[-1]['link'])
		elif action == "setsemester":
			if user == None or "semester" not in request.args:
				raise ValueError('Missing user or semester arg')
			semester_url = request.args["semester"]
			user.activeSemester = ndb.Key(urlsafe=semester_url)
			user.put()
		else:
			logging.error('unknown action=' + action)
			return "", 404

	if request.method == "POST" and len(request.form) > 0 and "action" in request.form:
		action=request.form["action"]
		if action == "saveattendance":
			if troop == None or scoutgroup == None or key_url == None:
				raise ValueError('Missing troop or group')

			meeting = ndb.Key(urlsafe=key_url).get()
			meeting.attendingPersons[:] = [] # clear the list
			for person_url in request.form["persons"].split(","):
				#logging.debug("person_url=%s", person_url)
				if len(person_url) > 0:
					person_key = ndb.Key(urlsafe=person_url)
					meeting.attendingPersons.append(person_key)
			meeting.put()
			return "ok"
		elif action == "addmeeting" or action == "updatemeeting":
			mname = request.form['name']
			mdate = request.form['date']
			mtime = request.form['starttime'].replace('.', ':')
			dtstring = mdate + "T" + mtime
			mduration = request.form['duration']
			dt = datetime.datetime.strptime(dtstring, "%Y-%m-%dT%H:%M")
			if action == "addmeeting":
				meeting = Meeting.getOrCreate(troop_key, 
					mname,
					dt,
					int(mduration))
			else:
				meeting = ndb.Key(urlsafe=key_url).get()

			meeting.name = mname
			meeting.datetime = dt
			meeting.duration = int(mduration)
			meeting.commit()
			return redirect(breadcrumbs[-1]['link'])
		elif action == "deletemeeting":
			meeting = ndb.Key(urlsafe=key_url).get()
			logging.debug("deleting meeting=%s", meeting.getname())
			meeting.delete()
			return redirect(breadcrumbs[-1]['link'])
		else:
			logging.error('unknown action=' + action)
			return "", 404

	# render main pages
	if scoutgroup == None:
		return render_template('index.html', 
			heading = section_title, 
			baselink = baselink,
			items = ScoutGroup.getgroupsforuser(user),
			breadcrumbs = breadcrumbs,
			env = env, 
			session = session)
	elif troop==None:
		section_title = 'Avdelningar'
		return render_template('troops.html',
			heading = section_title,
			baselink = baselink,
			scoutgroupinfolink = '/scoutgroupinfo/' + sgroup_url + '/',
			groupsummarylink = '/groupsummary/' + sgroup_url + '/',
			user = user,
			semesters = Semester.query(),
			troops = Troop.getTroopsForUser(sgroup_key, user),
			breadcrumbs = breadcrumbs,
			env = env,
			session = session)
	elif key_url!=None and key_url!="dak":
		meeting = ndb.Key(urlsafe=key_url).get()
		section_title = meeting.getname()
		trooplink = baselink
		baselink += key_url + "/"
		breadcrumbs.append({'link':baselink, 'text':section_title})

		return render_template('meeting.html',
			heading = section_title,
			baselink = baselink,
			existingmeeting = meeting,
			breadcrumbs = breadcrumbs,
			trooplink = trooplink,
			env = env, 
			session = session)
	else:
		meetingCount = 0
		sumMaleAttendenceCount = 0
		sumFemaleAttendenceCount = 0
		sumMaleLeadersAttendenceCount = 0
		sumFemaleLeadersAttendenceCount = 0
		noLeaderMeetingCount = 0
		tooSmallGroupMeetingCount = 0
		ageProblemCount = 0
		ageProblemDesc = []

		section_title = troop.getname()
		trooppersons = TroopPerson.getTroopPersonsForTroop(troop_key)
		meetings = Meeting.gettroopmeetings(troop_key)
		
		attendances = [] # [meeting][person]
		persons = []
		personsDict = {}
		for troopperson in trooppersons:
			personKey = troopperson.person
			person = troopperson.person.get()
			persons.append(person)
			personsDict[personKey] = person
		
		semester = troop.semester_key.get()
		year = semester.getyear()
		for meeting in meetings:
			maleAttendenceCount = 0
			femaleAttendenceCount = 0
			maleLeadersAttendenceCount = 0
			femaleLeadersAttendenceCount = 0
			meetingattendance = []
			for troopperson in trooppersons:
				isAttending = troopperson.person in meeting.attendingPersons
				meetingattendance.append(isAttending)
				if isAttending:
					person = personsDict[troopperson.person]
					age = person.getyearsoldthisyear(year)
					if troopperson.leader:
						if age >= 13 and age <= 100:
							if femaleLeadersAttendenceCount+maleLeadersAttendenceCount < 2:
								if person.female:
									femaleLeadersAttendenceCount += 1
								else:
									maleLeadersAttendenceCount += 1
						else:
							ageProblemCount += 1
							ageProblemDesc.append(person.getname() + ": " + str(age))
					else:
						if age >= 7 and age <= 25:
							if person.female:
								femaleAttendenceCount += 1
							else:
								maleAttendenceCount += 1
						else:
							ageProblemCount += 1
							ageProblemDesc.append(person.getname() + ": " + str(age))
					
			attendances.append(meetingattendance)
			totalAttendence = maleAttendenceCount+femaleAttendenceCount
			# max 40 people
			if totalAttendence > 40:
				surplusPeople = totalAttendence-40
				removedMen = min(maleAttendenceCount, surplusPeople)
				maleAttendenceCount -= removedMen
				surplusPeople -= removedMen
				femaleAttendenceCount -= surplusPeople

			maxLeaders = 1 if totalAttendence <= 10 else 2
			totalLeaders = femaleLeadersAttendenceCount+maleLeadersAttendenceCount
			if totalAttendence < 3:
				tooSmallGroupMeetingCount += 1
			else:
				if totalLeaders == 0:
					noLeaderMeetingCount += 1
				else:
					meetingCount += 1
					sumFemaleAttendenceCount += femaleAttendenceCount
					sumMaleAttendenceCount += maleAttendenceCount
					if totalLeaders > maxLeaders:
						if maleLeadersAttendenceCount > maxLeaders and femaleLeadersAttendenceCount == 0:
							maleLeadersAttendenceCount = maxLeaders
						elif maleLeadersAttendenceCount == 0 and femaleLeadersAttendenceCount > maxLeaders:
							femaleLeadersAttendenceCount = maxLeaders
						else:
							femaleLeadersAttendenceCount = maxLeaders / 2
							maxLeaders -= femaleLeadersAttendenceCount
							maleLeadersAttendenceCount = maxLeaders
						
					sumFemaleLeadersAttendenceCount += femaleLeadersAttendenceCount
					sumMaleLeadersAttendenceCount += maleLeadersAttendenceCount

		if key_url == "dak":
			dak = DakData()
			dak.foereningsNamn = scoutgroup.getname()
			dak.foreningsID = scoutgroup.foreningsID
			dak.organisationsnummer = scoutgroup.organisationsnummer
			dak.kommunID = scoutgroup.kommunID
			dak.kort.NamnPaaKort = troop.getname()
			# hack generate an "unique" id, if there is none
			if troop.rapportID == None or troop.rapportID == 0:
				troop.rapportID = random.randint(100, 1000000)
				troop.put()

			dak.kort.NaervarokortNummer = str(troop.rapportID)
			
			for tp in trooppersons:
				p = personsDict[tp.person]
				if tp.leader:
					dak.kort.ledare.append(Deltagare(str(p.key.id()), p.firstname, p.lastname, p.getpersonnr(), True, p.email, p.mobile))
				else:
					dak.kort.deltagare.append(Deltagare(str(p.key.id()), p.firstname, p.lastname, p.getpersonnr(), False))
				
			for m in meetings:
				sammankomst = Sammankomst(str(m.key.id()[:50]), m.datetime, m.duration, m.getname())
				for tp in trooppersons:
					isAttending = tp.person in m.attendingPersons
					if isAttending:
						p = personsDict[tp.person]
						if tp.leader:
							sammankomst.ledare.append(Deltagare(str(p.key.id()), p.firstname, p.lastname, p.getpersonnr(), True, p.email, p.mobile))
						else:
							sammankomst.deltagare.append(Deltagare(str(p.key.id()), p.firstname, p.lastname, p.getpersonnr(), False))
				
				dak.kort.Sammankomster.append(sammankomst)
			
			result = render_template('dak.xml', dak=dak)
			response = make_response(result)
			response.headers['Content-Type'] = 'application/xml'
			response.headers['Content-Disposition'] = 'attachment; filename=' + urllib.quote(str(dak.kort.NamnPaaKort), safe='') + '-' + semester.getname() + '.xml;'
			return response
		else:
			allowance = []
			allowance.append({'name':'Antal möten:', 'value':meetingCount})
			allowance.append({'name':'Deltagartillfällen', 'value':''})
			allowance.append({'name':'Kvinnor:', 'value':sumFemaleAttendenceCount})
			allowance.append({'name':'Män:', 'value':sumMaleAttendenceCount})
			allowance.append({'name':'Ledare Kvinnor:', 'value':sumFemaleLeadersAttendenceCount})
			allowance.append({'name':'Ledare Män:', 'value':sumMaleLeadersAttendenceCount})
			if noLeaderMeetingCount > 0:
				allowance.append({'name':'Antal möten utan ledare', 'value':noLeaderMeetingCount})
			if tooSmallGroupMeetingCount > 0:
				allowance.append({'name':'Antal möten med för få deltagare', 'value':tooSmallGroupMeetingCount})
			if ageProblemCount > 0:
				allowance.append({'name':'Ålder utanför intervall:', 'value':ageProblemCount})
			if len(ageProblemDesc) > 0:
				ageProblemDescStr = ','.join(ageProblemDesc[:3])
				if len(ageProblemDesc) > 3:
					ageProblemDescStr += "..."
				allowance.append({'name':'', 'value':ageProblemDescStr})
				
			return render_template('troop.html',
				heading = section_title,
				semestername = semester.getname(),
				baselink = '/persons/' + scoutgroup.key.urlsafe() + '/',
				persons = persons,
				trooppersons = trooppersons,
				meetings = meetings,
				attendances = attendances,
				breadcrumbs = breadcrumbs,
				allowance = allowance,
				troop = troop,
				user = user,
				env = env, 
				session = session)

@app.route('/persons')
@app.route('/persons/')
@app.route('/persons/<sgroup_url>')
@app.route('/persons/<sgroup_url>/')
@app.route('/persons/<sgroup_url>/<person_url>')
@app.route('/persons/<sgroup_url>/<person_url>/')
@app.route('/persons/<sgroup_url>/<person_url>/<action>')
def persons(sgroup_url=None, person_url=None, action=None):
	user = UserPrefs.current()
	if not user.hasAccess():
		return "denied", 403

	session = get_current_session()
	breadcrumbs = [{'link':'/', 'text':'Hem'}]
	
	section_title = u'Personer'
	breadcrumbs.append({'link':'/persons', 'text':section_title})
	baselink='/persons/'

	scoutgroup = None
	if sgroup_url!=None:
		sgroup_key = ndb.Key(urlsafe=sgroup_url)
		scoutgroup = sgroup_key.get()
		baselink+=sgroup_url+"/"
		breadcrumbs.append({'link':baselink, 'text':scoutgroup.getname()})

	person = None
	if person_url!=None:
		person_key = ndb.Key(urlsafe=person_url)
		person = person_key.get()
		baselink+=person_url+"/"
		section_title = person.getname()
		breadcrumbs.append({'link':baselink, 'text':section_title})
	
	if action != None:
		if action == "deleteperson" or action == "addbackperson":
			person.removed = action == "deleteperson"
			person.put() # we only mark the person as removed
			if person.removed:
				tps = TroopPerson.query(TroopPerson.person == person.key).fetch()
				for tp in tps:
					tp.delete()
			return redirect(breadcrumbs[-1]['link'])
		elif action == "removefromtroop" or action == "setasleader" or action == "removeasleader":
			troop_key = ndb.Key(urlsafe=request.args["troop"])
			tps = TroopPerson.query(TroopPerson.person == person.key, TroopPerson.troop == troop_key).fetch(1)
			if len(tps) == 1:
				tp = tps[0]
				if action == "removefromtroop":
					tp.delete()
				else:
					tp.leader = (action == "setasleader")
					tp.put()
		elif action == "addtowaitinglist":
			scoutgroup = person.scoutgroup.get()
			troop = None
			tps = TroopPerson.query(TroopPerson.person == person.key).fetch(1)
			if len(tps) == 1:
				troop = tps[0].troop.get()
			scoutgroup = person.scoutgroup.get()
			if scoutgroup.canAddToWaitinglist():
				if scoutnet.AddPersonToWaitinglist(
						scoutgroup,
						person.firstname,
						person.lastname,
						person.personnr,
						person.email,
						person.street,
						person.zip_code,
						person.zip_name,
						person.mobile,
						person.phone,
						troop):
					person.notInScoutnet = False
					person.put()
		else:
			logging.error('unknown action=' + action)
			abort(404)
			return ""
		
	# render main pages
	if scoutgroup==None:
		return render_template('index.html', 
			heading = section_title, 
			baselink = baselink,
			items = ScoutGroup.getgroupsforuser(user),
			breadcrumbs = breadcrumbs,
			username = user.getname(),
			env = env,
			session = session)
	elif person==None:
		section_title = 'Personer'
		
		items = Person.query(Person.scoutgroup == sgroup_key).order(Person.firstname, Person.lastname).fetch(), # TODO: memcache
		letters = []

		for persons in items:
			for person in persons:
				letters.append(person.firstname[0])

		letters = sorted(set(letters))

		return render_template('memberlist.html',
			heading = section_title,
			baselink = baselink,
			items = items,
			breadcrumbs = breadcrumbs,
			username = user.getname(),
			letters = letters,
			env = env,
			session = session)
	else:
		troops = Troop.getTroopsForUser(sgroup_key, user)
		available_troops = []
		
		for troop in troops:
			available_troops.append([troop.key.string_id(),
				troop.name, 
				'/start/' + scoutgroup.key.urlsafe() + '/' + troop.key.urlsafe() + '/' + person.key.urlsafe()+'?action=addperson'])

		return render_template('person.html',
			heading = section_title,
			baselink = '/persons/' + scoutgroup.key.urlsafe() + '/',
			trooppersons = TroopPerson.query(TroopPerson.person == person.key).fetch(), # TODO: memcache,
			available_troops = available_troops,
			ep = person,
			scoutgroup = scoutgroup,
			breadcrumbs = breadcrumbs,
			env = env,
			session = session)
	
@app.route('/scoutgroupinfo/<sgroup_url>')
@app.route('/scoutgroupinfo/<sgroup_url>/', methods = ['POST', 'GET'])
def scoutgroupinfo(sgroup_url):
	user = UserPrefs.current()
	
	if not user.canImport():
		return "denied", 403
	
	session = get_current_session()
	breadcrumbs = [{'link':'/', 'text':'Hem'}]
	baselink = "/scoutgroupinfo/"
	section_title = "Kårinformation"
	scoutgroup = None
	
	if sgroup_url != None:
		sgroup_key = ndb.Key(urlsafe=sgroup_url)
		scoutgroup = sgroup_key.get()
		baselink += sgroup_url+"/"
		breadcrumbs.append({'link':baselink, 'text':scoutgroup.getname()})
	
	if request.method == "POST":
		logging.info("POST, %s" % str(request.form))
		scoutgroup.organisationsnummer = request.form['organisationsnummer'].strip()
		scoutgroup.foreningsID = request.form['foreningsID'].strip()
		scoutgroup.scoutnetID = request.form['scoutnetID'].strip()
		scoutgroup.kommunID = request.form['kommunID'].strip()
		scoutgroup.apikey_waitinglist = request.form['apikey_waitinglist'].strip()
		scoutgroup.apikey_all_members = request.form['apikey_all_members'].strip()
		scoutgroup.put()
		logging.info("Done, redirect to: %s", breadcrumbs[-1]['link'])
		
		if "import" in request.form:
			result = RunScoutnetImport(scoutgroup.scoutnetID, scoutgroup.apikey_all_members, user, Semester.getOrCreateCurrent())
			return render_template('table.html', tabletitle="Importresultat", items=result, rowtitle='Result', breadcrumbs=breadcrumbs,env=env,session=session)
		else:
			return redirect_with_message(breadcrumbs[-1]['link'], 'Inställningarna har sparats.', 'success')
	else:
		return render_template('scoutgroupinfo.html',
			heading = section_title,
			baselink = baselink,
			scoutgroup = scoutgroup,
			breadcrumbs = breadcrumbs,
			env = env,
			session = session)
			

@app.route('/groupsummary/<sgroup_url>')
@app.route('/groupsummary/<sgroup_url>/')
def scoutgroupsummary(sgroup_url):
	user = UserPrefs.current()
	if not user.canImport():
		return "denied", 403
	if sgroup_url is None:
		return "missing group", 404

	session = get_current_session()
	sgroup_key = ndb.Key(urlsafe=sgroup_url)
	scoutgroup = sgroup_key.get()
	breadcrumbs = [{'link':'/', 'text':'Hem'}]
	baselink = "/groupsummary/" + sgroup_url
	section_title = "Föreningsredovisning - " + scoutgroup.getname()
	breadcrumbs.append({'link':baselink, 'text':section_title})
	class Item():
		age = 0
		women = 0
		men = 0
		def __init__(self, age, women=0, men=0):
			self.age = age
			self.women = women
			self.men = men

	year = datetime.datetime.now().year - 1 # previous year
	women = 0
	men = 0
	startage = 7
	endage = 25
	ages = [Item('0 - 6')]
	ages.extend([Item(i) for i in range(startage, endage+1)])
	ages.append(Item('26 - 64'))
	ages.append(Item('65 -'))
	leaders = [Item(u't.o.m. 25 år'), Item(u'över 25 år')]
	boardmebers = [Item('')]
	
	for person in Person.query(Person.scoutgroup==sgroup_key, Person.removed==False).fetch():
		age = person.getyearsoldthisyear(year)
		index = 0
		if 7 <= age <= 25:
			index = age-startage + 1
		elif age < 7:
			index = 0
		elif 26 <= age <= 64:
			index = endage - startage + 2
		else:
			index = endage - startage + 3
			
		if person.female:
			women += 1
			ages[index].women += 1
		else:
			men += 1
			ages[index].men += 1

		if person.isBoardMember():
			if person.female:
				boardmebers[0].women += 1
			else:
				boardmebers[0].men += 1
		if person.isLeader():
			index = 0 if age <= 25 else 1
			if person.female:
				leaders[index].women += 1
			else:
				leaders[index].men += 1

	ages.append(Item("Totalt", women, men))
	return render_template('groupsummary.html', ages=ages, boardmebers=boardmebers, leaders=leaders, breadcrumbs=breadcrumbs, env=env, session=session)


@app.route('/getaccess/', methods = ['POST', 'GET'])
def getaccess():
	user = UserPrefs.current()
	session = get_current_session()
	breadcrumbs = [{'link':'/', 'text':'Hem'}]
	baselink = "/getaccess/"
	section_title = "Access"
	breadcrumbs.append({'link':baselink, 'text':section_title})
	if request.method == "POST":
		adminEmails = [u.email for u in UserPrefs.query(UserPrefs.hasadminaccess==True).fetch()]
		if len(adminEmails) > 0:
			scoutgroup_name = request.form.get('sg').strip()
			mail.send_mail(sender=user.email,
			to=','.join(adminEmails),
			subject="Användren: " + user.getname() + " vill ha access.\nKår: " + scoutgroup_name,
			body="""""")	
		return redirect('/')
	else:
		return render_template('getaccess.html',
			baselink = baselink,
			breadcrumbs = breadcrumbs,
			env = env,
			session = session)

@app.route('/import')
@app.route('/import/', methods = ['POST', 'GET'])
def import_():
	user = UserPrefs.current()
	if not user.canImport():
		return "denied", 403

	session = get_current_session()
	breadcrumbs = [{'link':'/', 'text':'Hem'},
				   {'link':'/import', 'text':'Import'}]

	currentSemester = Semester.getOrCreateCurrent()
	semesters=[currentSemester]
	semesters.extend(Semester.query(Semester.key!=currentSemester.key))
	if request.method != 'POST':
		return render_template('updatefromscoutnetform.html', heading="Import", breadcrumbs=breadcrumbs, user=user, semesters=semesters, env=env, session=session)

	api_key = request.form.get('apikey').strip()
	groupid = request.form.get('groupid').strip()
	semester=ndb.Key(urlsafe=request.form.get('semester')).get()
	result = RunScoutnetImport(groupid, api_key, user, semester)
	return render_template('importresulttable.html', 
							items = result, 
							tabletitle = "Importresultat", 
							rowtitle = 'Resultatlogg', 
							breadcrumbs = breadcrumbs, 
							env = env, 
							session = session)


@app.route('/admin')
@app.route('/admin/')
def admin():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	breadcrumbs = [{'link':'/', 'text':'Hem'},
				   {'link':'/admin', 'text':'Admin'}]
	return render_template('admin.html', heading="Admin", breadcrumbs=breadcrumbs, username=user.getname(), env=env, session=session)

@app.route('/admin/access/')
@app.route('/admin/access/<userprefs_url>')
@app.route('/admin/access/<userprefs_url>/', methods = ['POST', 'GET'])
def adminaccess(userprefs_url=None):
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	section_title = u'Hem'
	baselink = '/'
	breadcrumbs = [{'link':baselink, 'text':section_title}]
	
	section_title = u'Admin'
	baselink += 'admin/'
	breadcrumbs.append({'link':baselink, 'text':section_title})

	section_title = u'Access'
	baselink += 'access/'
	breadcrumbs.append({'link':baselink, 'text':section_title})

	if userprefs_url != None:
		userprefs = ndb.Key(urlsafe=userprefs_url).get()
		if request.method == 'POST':
			userprefs.hasaccess = request.form.get('hasAccess') == 'on'
			userprefs.hasadminaccess = request.form.get('hasAdminAccess') == 'on'
			userprefs.groupadmin = request.form.get('groupadmin') == 'on'
			userprefs.canimport = request.form.get('canImport') == 'on'
			sgroup_key = None
			if len(request.form.get('groupaccess')) != 0:
				sgroup_key = ndb.Key(urlsafe=request.form.get('groupaccess'))
			userprefs.groupaccess = sgroup_key
			userprefs.put()
			return redirect_with_message('/admin/access/', "Användare "+userprefs.getname()+" sparad.", "success")
		else:
			section_title = userprefs.getname()
			baselink += userprefs_url + '/' 
			breadcrumbs.append({'link':baselink, 'text':section_title})
			return render_template('userprefs.html',
				heading = section_title,
				baselink = baselink,
				userprefs = userprefs,
				breadcrumbs = breadcrumbs,
				scoutgroups = ScoutGroup.query().fetch(),
				env = env,
				session = session)

	users = UserPrefs().query().fetch()
	return render_template('userlist.html',
		heading = section_title,
		baselink = baselink,
		users = users,
		breadcrumbs = breadcrumbs,
		env = env,
		session = session)

@app.route('/groupaccess')
@app.route('/groupaccess/')
@app.route('/groupaccess/<userprefs_url>')
def groupaccess(userprefs_url=None):
	user = UserPrefs.current()
	if not user.isGroupAdmin():
		return "denied", 403
	
	session = get_current_session()
	section_title = u'Hem'
	baselink = '/'
	breadcrumbs = [{'link':baselink, 'text':section_title}]
	
	if not user.groupaccess:
		return redirect_with_message('/', u"Ditt användarkonto är inte associerat med någon kår. Kontakta administratören.", "danger")

	section_title = u'Behörighet ' + user.groupaccess.get().getname()
	baselink += 'groupaccess/'
	breadcrumbs.append({'link':baselink, 'text':section_title})

	# AJAX call, return empty response.
	if userprefs_url != None:
		userprefs = ndb.Key(urlsafe=userprefs_url).get()
		groupaccessurl = request.args["setgroupaccess"]
		if groupaccessurl == 'None':
			userprefs.groupaccess = None
		else:
			userprefs.groupaccess = ndb.Key(urlsafe=groupaccessurl)
			userprefs.hasaccess = True
		userprefs.put()
		return "ok", 200
	
	users = UserPrefs().query(UserPrefs.groupaccess == None).fetch()
	users.extend(UserPrefs().query(UserPrefs.groupaccess == user.groupaccess).fetch())
	
	return render_template('groupaccess.html',
		heading = section_title,
		baselink = baselink,
		users = users,
		breadcrumbs = breadcrumbs,
		mygroupurl = user.groupaccess.urlsafe(),
		mygroupname = user.groupaccess.get().getname(),
		env = env,
		session = session)

@app.route('/admin/deleteall/')
def dodelete():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	DeleteAllData() # uncomment to enable this
	return redirect('/admin/')

	
@app.route('/admin/settroopsemester/')
def settroopsemester():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	dosettroopsemester()
	return redirect('/admin/')
	
@app.route('/admin/fixsgroupids/')
def fixsgroupids():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	dofixsgroupids()
	return redirect('/admin/')
	

@app.route('/admin/updateschemas')
def doupdateschemas():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	UpdateSchemas()
	return redirect('/admin/')
	
@app.route('/admin/setcurrentsemester')
def setcurrentsemester():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	semester = Semester.getOrCreateCurrent()
	for u in UserPrefs.query().fetch():
		u.activeSemester = semester.key
		u.put()

	return redirect_with_message('/admin/', 'Aktiv termin är nu ' + semester.getname(), 'success')
	
@app.route('/admin/autoGroupAccess')
def autoGroupAccess():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403
	users = UserPrefs().query().fetch()
	for u in users:
		u.attemptAutoGroupAccess()

	session = get_current_session()
	return "done"


@app.route('/admin/backup')
@app.route('/admin/backup/')
def dobackup():
	user = UserPrefs.current()
	if not user.isAdmin():
		return "denied", 403

	session = get_current_session()
	response = make_response(GetBackupXML())
	response.headers['Content-Type'] = 'application/xml'
	thisdate = datetime.datetime.now()
	response.headers['Content-Disposition'] = 'attachment; filename=skojjt-backup-' + str(thisdate.isoformat()) + '.xml'
	return response

@app.route('/admin/cleanup_sessions')
def cleanup_sessions():
	while not delete_expired_sessions():
		pass

	return "ok", 200

@app.errorhandler(404)
def page_not_found(e):
	return render_template('notfound.html'), 404

@app.errorhandler(403)
def access_denied(e):
	return render_template('403.html'), 403

@app.errorhandler(500)
def serverError(e):
	logging.error("Error 500:%s", str(e))
	return render_template('error.html', error=str(e)), 500

def redirect_with_message(url, message, urgency = 'info'):
	get_current_session()['message'] = message
	get_current_session()['message_urgency'] = urgency
	return redirect(url)

# Custom context processor to clear message in session
# after it has been displayed in layout.html
@app.context_processor
def utility_processor():
	def clear_message(s):
		if s.has_key('message'):
			del s['message']
		if s.has_key('message_urgency'):
			del s['message_urgency']
		return ''
	return dict(clear_message=clear_message)
