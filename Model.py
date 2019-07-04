import os
import re
import sys
import datetime
import random
import operator
from metaphone import doublemetaphone

import Utils
from Excel import GetExcelReader
from CountryIOC import uci_country_codes, uci_country_codes_set, ioc_from_country, country_from_ioc

countryTranslations = {
	'England':						'United Kingdom',
	'Great Britain':				'United Kingdom',
	'Scotland':						'United Kingdom',
	'Wales':						'United Kingdom',
	'United States of America': 	'United States',
	'Hong Kong, China':				'Hong Kong',
}
countryTranslations = { k.upper(): v for k, v in countryTranslations.items() }

specialNationCodes = uci_country_codes
specialNationCodes = { k.upper(): v for k, v in specialNationCodes.items() }

non_digits = re.compile( u'[^0-9]' )
all_quotes = re.compile( u"[\u2019\u0027\u2018\u201C\u201D`\"]" )
all_stars = re.compile( u"[*\u2605\u22C6]" )
def normalize_name( s ):
	s = all_quotes.sub( u"'", u'{}'.format(s).replace(u'(JR)',u'') )
	s = all_stars.sub( u"", s )
	return s.strip()
	
def normalize_name_lookup( s ):
	return Utils.removeDiacritic(normalize_name(s)).upper()

def format_uci_id( uci_id ):
	if not uci_id:
		return u''
	return u' '.join( uci_id[i:i+3] for i in range(0, len(uci_id), 3) )
	
def parse_name( name ):
	name = normalize_name( name )
	if ',' in name:
		# Comma separated Last, First.
		last_name, first_name = [n.strip() for n in name.split(',', 2)]
		return first_name, last_name
	
	# Check that there are at least two consecutive capitalized characters in the name somewhere.
	for i in range(len(name)-1):
		chars2 = name[i:i+1]
		if chars2.isalpha() and chars2 == chars2.upper():
			break
	else:
		raise ValueError( u'invalid name: last name must be capitalized: {}'.format( name ) )
	
	# Find the last alpha character.
	cLast = 'C'
	for i in range(len(name)-1, -1, -1):
		if name[i].isalpha():
			cLast = name[i]
			break
	
	if name[:2].upper() == name[:2]:
		# First two characters are capitalized.
		# Assume the name is of the form LAST NAME First Name.
		# Find the last upper-case letter preceding a space.  Assume that is the last char in the last_name.
		j = 0
		i = 0
		while 1:
			i = name.find( u' ', i )
			if i < 0:
				if not j:
					j = len(name)
				break
			cPrev = name[i-1]
			if cPrev.isalpha() and cPrev.isupper():
				j = i
			i += 1
		return name[j:], name[:j]
	elif name[-2:].upper() == name[-2:]:
		# Last two characters are capitalized.
		# Assume the name field is of the form First Name LAST NAME
		# Find the last lower-case letter preceding a space.  Assume that is the last char in the first_name.
		j = 0
		i = 0
		while 1:
			i = name.find( u' ', i )
			if i < 0:
				break
			cPrev = name[i-1]
			if cPrev.isalpha() and cPrev.islower():
				j = i
			i += 1
		return name[:j], name[j:]
	else:
		# Assume name is of form First Last where the first name is separated by the first space.
		i = name.find( u' ' )
		if i < 0:
			return u'', name
		else:
			return name[:i], name[i:]
	raise ValueError( u'invalid name: cannot parse first, last name: {}'.format( name ) )

class Result( object ):
	ByPoints, ByPosition = (0, 1)
	
	Fields = (
		'bib',
		'first_name', 'last_name',
		'team',
		'team_code',
		'uci_id',
		'license',
		'nation',
		'nation_code',
		'city',
		'state_prov',
		'category',
		'age',
		'date_of_birth',
		'points', 'position',
		'row'
	)
	NumericFields = set([
		'bib', 'age', 'points', 'position'
	])
	KeyFields = set([
		'first_name', 'last_name',
		'uci_id', 'license', 'age',
	])
	
	IgnorePosition = set(['DNF', 'DNS', 'NP', 'DQ', 'DSQ', 'DNP'])

	def __init__( self, **kwargs ):
		
		if 'name' in kwargs and 'last_name' not in kwargs:
			kwargs['first_name'], kwargs['last_name'] = parse_name( kwargs['name'] )
		
		for f in self.Fields:
			setattr( self, f, kwargs.get(f, None) )
			
		if self.license is not None:
			self.license = u'{}'.format(self.license).strip()
			
		if self.row:
			try:
				self.row = int(self.row)
			except ValueError:
				self.row = None
				
		if self.points:
			try:
				self.points = float(self.points)
			except ValueError:
				self.points = None
		
		if self.position:
			if self.position in self.IgnorePosition:
				self.position = None
				self.points = None
			else:
				self.position = non_digits.sub( u'', u'{}'.format(self.position) )
				try:
					self.position = int(self.position)
				except ValueError:
					self.position = None
		
		if self.last_name:
			self.last_name = normalize_name( self.last_name )
			
		if self.first_name:
			self.first_name = normalize_name( self.first_name )
		
		if self.team:
			self.team = normalize_name( self.team )
		
		if self.team_code:
			self.team_code = normalize_name( self.team_code )
		
		# Check for swapped nation/nation_code
		if self.nation:
			if len(self.nation) == 3 and country_from_ioc(self.nation):
				self.nation_code = self.nation
				self.nation = country_from_ioc(self.nation)
		
		# Get the 3-digit nation code from the nation name.
		if self.nation:
			self.nation = u'{}'.format(self.nation).replace( u'&', u'and' ).strip()
			self.nation = countryTranslations.get(self.nation.upper(), self.nation)
			if not self.nation_code:
				self.nation_code = ioc_from_country( self.nation )
				if not self.nation_code:
					raise KeyError( u'cannot find nation_code from nation: "{}" ({}, {})'.format(self.nation, self.last_name, self.first_name) )
		
		if self.nation_code:
			self.nation_code = self.nation_code.upper()
		
		if self.date_of_birth and not self.age:
			self.age = datetime.date.today().year - self.date_of_birth.year		# Competition age.
		
		if self.age is not None:
			try:
				self.age = int(self.age)
			except ValueError:
				raise ValueError( u'invalid age: {} ({}, {})'.format(self.age, self.last_name, self.first_name) )
				
		assert self.date_of_birth is None or isinstance(self.date_of_birth, datetime.date), 'invalid Date of Birth'
		
		if self.uci_id is not None:
			self.uci_id = u'{}'.format(self.uci_id).replace( u' ', '' )
			try:
				self.uci_id = u'{}'.format( int(self.uci_id) )
			except ValueError:
				raise ValueError( u'uci_id: "{}" contains non-digits ({}, {})'.format(self.uci_id, self.last_name, self.first_name) )
			if self.uci_id == 0:
				self.uci_id = None
		
		self.cmp_policy = None
	
	def __repr__( self ):
		return '({})'.format( Utils.removeDiacritic( self.as_str(self.Fields) ) )
		
	def as_str( self, fields=None ):
		fields = fields or self.Fields
		data = [ u'{}'.format(getattr(self,f).upper() if f == 'last_name' else getattr(self,f)) for f in fields if getattr(self,f,None) is not None and f != 'row' ]
		for i in range(len(data)):
			d = data[i]
			for t, fmt in ((int, u'{}'), (float, u'{:.3f}')):
				try:
					d = fmt.format(t(d))
					break
				except ValueError:
					pass
			else:
				d = u'"{}"'.format( d )
			data[i] = d
			
		return u','.join( data )
		
	def as_list( self, fields=None ):
		lines = []
		fields = fields or (
			'first_name', 'last_name',
			'team',
			'team_code',
			'uci_id',
			'license',
			'nation',
			'nation_code',
			'points', 'position',
			'row'
		)
		fLast = None
		for f in fields:
			if f in self.KeyFields:
				v = getattr( self, f )
				if v is not None:
					if f == 'last_name':
						v = v.upper()
					if f in ('first_name', 'last_name'):
						if f == 'last_name' and fLast == 'first_name':
							lines[-1] += u' {}'.format(v)
						else:
							lines.append( u'{}'.format(v) )
					else:
						if f == 'team':
							v = u'{}'.format(v)
							if len(v) > 30:
								v = v[:27] + u'...'
						lines.append( u'{}={}'.format(f, v) )
				fLast = f
		fLast = None
		for f in fields:
			if f not in self.KeyFields:
				v = getattr( self, f )
				if v is not None:
					if f == 'last_name':
						v = v.upper()
					if f in ('first_name', 'last_name'):
						if f == 'last_name' and fLast == 'first_name':
							lines[-1] += u' {}'.format(v)
						else:
							lines.append( u'{}'.format(v) )
					else:
						lines.append( u'{}={}'.format(f, v) )
				fLast = f
		return lines
	
	@property
	def full_name( self ):
		return u'{} {}'.format( self.first_name, self.last_name )
	
	def get_key( self ):
		if self.cmp_policy == self.ByPoints:
			return -(self.points or 0)
		elif self.cmp_policy == self.ByPosition:
			return self.position or 999999
		assert False, 'Invalid cmp_policy'
		
	def get_sort_key( self ):
		return (self.get_key(), self.row)
		
	def get_value( self ):
		if self.cmp_policy == self.ByPoints:
			return self.points
		elif self.cmp_policy == self.ByPosition:
			return self.position
		assert False, 'Invalid cmp_policy'

reAlpha = re.compile( '[^A-Z]+' )
header_sub = {
	u'RANK':			u'POSITION',
	u'POS':				u'POSITION',
	u'PLACE':			u'POSITION',
	u'BIBNUM':			u'BIB',
	u'BIBNUMBER':		u'BIB',
	u'NUM':				u'BIB',
	u'LICENSENUMBER':	u'LICENSE',
	u'LIC':				u'LICENSE',
	u'DOB':				u'DATEOFBIRTH',
	u'FIRST':			u'FIRSTNAME',
	u'LAST':			u'LASTNAME',
	u'PROV':			u'STATEPROV',
	u'PROVINCE':		u'STATEPROV',
	u'STATE':			u'STATE',
}
def scrub_header( h ):
	h = reAlpha.sub( '', Utils.removeDiacritic(u'{}'.format(h)).upper() )
	return header_sub.get(h, h)

def soundalike_match( s1, s2 ):
	dmp1 = doublemetaphone( s1.replace('-','').encode('utf8') )
	dmp2 = doublemetaphone( s2.replace('-','').encode('utf8') )
	return any( v in dmp1 for v in dmp2 )
	
class FindResult( object ):
	NoMatch, Success, SuccessSoundalike, MultiMatch = range(4)

	def __init__( self, search, matches, source, soundalike ):
		self.search = search
		self.matches = sorted(matches or [], key = lambda r: r.row)
		self.source = source
		self.soundalike = soundalike
	
	def get_key( self ):
		if len(self.matches) == 1:
			return self.matches[0].get_key()
		return 0 if self.source.cmp_policy == Result.ByPoints else 999999
	
	def get_sort_key( self ):
		try:
			row = self.matches[0].row
		except:
			row = 999999
		return (self.get_key(), row)
	
	def get_value( self ):
		if not self.matches:
			return u''
		if len(self.matches) == 1:
			return self.matches[0].get_value()
		return u"\u2605" * len(self.matches)
	
	def get_status( self ):
		if not self.matches:
			return self.NoMatch
		if len(self.matches) == 1:
			if self.soundalike:
				return self.SuccessSoundalike
			return self.Success
		return self.MultiMatch
	
	def __repr__( self ):
		return u'{}'.format(self.get_value())
	
	def get_name_status( self ):
		if not self.Success or len(self.matches) != 1:
			return 0
		name_1 = self.search.first_name, self.search.last_name
		name_2 = self.matches[0].first_name, self.matches[0].last_name
		if all(n1 == n2 for n1, n2 in zip(name_1, name_2)):
			return 0
		if all(soundalike_match(n1, n2) for n1, n2 in zip(name_1, name_2)):
			return 1
		return 2
	
	def get_message( self, fields=None ):
		matchName = {
			self.Success:			_('Success'),
			self.SuccessSoundalike: _('Soundalike Match'),
			self.MultiMatch:		_('Multiple Matches'),
			self.NoMatch:			_('No Match'),
		}[self.get_status()]
		matches = u'\n'.join( u', '.join(r.as_list(fields)) for r in self.matches )
		
		message = u'{matchName}: "{sheet_name}"\n\n{registration}:\n{registrationData}\n\n{matches}:\n{matchesData}'.format(
			matchName=matchName, sheet_name=self.source.sheet_name,
			registration=_('Registration'), registrationData=u', '.join(self.search.as_list(fields)),
			matches=_('Matches'), matchesData=matches,
		)
		return message

def validate_uci_id( uci_id ):
	if not uci_id:
		return
		
	uci_id = u'{}'.format(uci_id).upper().replace(u' ', u'')
	
	if not uci_id.isdigit():
		raise ValueError( u'uci id "{}" must be all digits'.format(uci_id) )
	
	if uci_id.startswith('0'):
		raise ValueError( u'uci id "{}" must not start with zero'.format(uci_id) )
	
	if len(uci_id) != 11:
		raise ValueError( u'uci id "{}" must be 11 digits'.format(uci_id) )
		
	if int(uci_id[:-2]) % 97 != int(uci_id[-2:]):
		raise ValueError( u'uci id "{}" check digit error'.format(uci_id) )

class Source( object ):
	Indices = (
		'by_license', 'by_uci_id',
		'by_last_name', 'by_first_name',
		'by_mp_last_name', 'by_mp_first_name',
		'by_nation_code', 'by_date_of_birth', 'by_age',
	)
	def __init__( self, fname, sheet_name, soundalike=True, useUciId=True, useLicense=True ):
		self.fname = fname
		self.sheet_name = sheet_name
		self.soundalike = soundalike
		self.useUciId = useUciId
		self.useLicense = useLicense
		self.results = []
		self.hasField = set()
		self.cmp_policy = None
		self.debug = False
		for i in self.Indices:
			setattr( self, i, {} )
		self._field_from_index = {}
	
	def empty( self ):
		return not self.results
	
	def field_from_index( self, i ):
		try:
			return self._field_from_index[i]
		except KeyError:
			self._field_from_index[i] = i[6:] if i.startswith('by_mp_') else i[3:]
			return self._field_from_index[i]
		
	def get_cmp_policy_field( self ):
		if self.cmp_policy == Result.ByPoints:
			return 'points'
		elif self.cmp_policy == Result.ByPosition:
			return 'position'
		else:
			return None
		
	def read( self, reader ):
		header_fields = ['name'] + list(Result.Fields)
		dCur = datetime.date.today()
		header_map = {}
		errors = []
		for row_number, row in enumerate(reader.iter_list(self.sheet_name)):
			if not row:
				continue
			
			# Map the column headers to the standard fields.
			if not header_map:
				header_scrub = { scrub_header(h):h for h in header_fields }
				for c, v in enumerate(row):
					rv = scrub_header( v )
					if rv in header_scrub:
						header_map[header_scrub[rv]] = c
				continue
		
			try:
				if all( not row[i] for i in range(3) ):
					continue
			except IndexError:
				continue
		
			# Create a Result from the row.
			row_fields = {}
			for field, column in header_map.items():
				try:
					row_fields[field] = row[column]
				except IndexError:
					pass
			
			# If points and position are not specified, use the row_number as the position.
			if 'points' not in row_fields and 'position' not in row_fields:
				row_fields['position'] = row_number + 1
				
			row_fields['row'] = row_number + 1
				
			try:
				result = Result( **row_fields )
			except Exception as e:
				errors.append( u'{} - row {} - {}'.format(self.sheet_name, row_number+1, e) )
				continue
				
			if 'uci_id' in header_map:
				try:
					validate_uci_id( result.uci_id )
				except Exception as e:
					errors.append( u'{} - row {} - Warning: {}'.format(self.sheet_name, row_number+1, e) )
			
			result.row_number = row_number
			
			if 'license' in header_map and not result.license:
				errors.append( u'{} - row {} - Warning: {} ({}, {})'.format(self.sheet_name, row_number+1, u'missing license', result.last_name, result.first_name) )
		
			if 'uci_id' in header_map and not result.uci_id:
				errors.append( u'{} - row {} - Warning: {} ({}, {})'.format(self.sheet_name, row_number+1, u'missing UCI ID', result.last_name, result.first_name) )
		
			self.add( result )
		
		self.cmp_policy = Result.ByPoints if 'points' in self.hasField else Result.ByPosition
		for r in self.results:
			r.cmp_policy = self.cmp_policy
		
		return errors
	
	def get_ordered_fields( self ):
		return tuple(f for f in Result.Fields if f in self.hasField and f not in ('points', 'position', 'row'))
	
	def randomize_positions( self ):
		positions = list(range( 1, len(self.results)+1 ))
		random.seed( 0xededed )
		random.shuffle( positions )
		self.cmp_policy = Result.ByPosition
		for i, r in enumerate(self.results):
			r.cmp_policy = self.cmp_policy
			r.position = positions[i]

	def add( self, result ):
		self.results.append( result )
		
		'''
		'by_license', 'by_uci_id',
		'by_last_name', 'by_first_name',
		'by_mp_last_name', 'by_mp_first_name',
		'by_nation_code', 'by_date_of_birth', 'by_age',
		'''
		
		for field in Result.Fields:
			if getattr( result, field, None ):
				self.hasField.add( field )
		
		for idx_name in self.Indices:
			field = self.field_from_index(idx_name)
			v = getattr( result, field, None )
			if not v:
				continue
			idx = getattr( self, idx_name )			
			if idx_name.startswith( 'by_mp_' ):	# Initialize a doublemetaphone (soundalike) index.
				for mp in doublemetaphone(v.replace('-','').encode('utf8')):
					if mp:
						try:
							idx[mp].append( result )
						except KeyError:
							idx[mp] = [result]
			else:								# Initialize a regular field index.
				assert idx_name != 'by_license' or v not in idx, 'Duplicate license: {}'.format(v)
				try:
					key = normalize_name_lookup(v)
				except:
					key = v					
				try:
					idx[key].append( result )
				except KeyError:
					idx[key] = [result]
	
	def get_match_fields( self, source ):
		indices = (
			('by_uci_id',),
			('by_license',),
			('by_last_name', 'by_first_name', 'by_nation_code', 'by_age', ),
			('by_last_name', 'by_first_name', 'by_age', ),
			('by_last_name', 'by_first_name',),
		)
		for pi in indices:
			if all( (self.field_from_index(i) in self.hasField) and (self.field_from_index(i) in source.hasField) for i in pi ):
				return tuple( self.field_from_index(i) for i in pi )
		return []
		
	def has_all_index_fields( self, search, indices ):
		return all( self.field_from_index(i) in self.hasField and getattr(search, self.field_from_index(i), None) is not None for i in indices )
			
	def match_indices( self, search, indices ):
		# Look for a set intersection of one element between all source criteria.
		
		if self.debug: print ( 'match_indices: searchKeys=', indices )
		
		soundalike = False
		setCur = None
		for idx_name in indices:
			if self.debug: print ( "match_indices: matching on key:", idx_name )
			idx = getattr( self, idx_name )
			v = getattr( search, self.field_from_index(idx_name), None )
			if not v or not idx:
				setCur = None
				if self.debug: print ( 'match_indices: missing attribute' )
				break

			try:
				v = normalize_name_lookup( v )
			except:
				pass
				
			if self.debug: print ( 'match_indices: value=', v )
			
			found = set()
			if idx_name.startswith( 'by_mp_' ):
				soundalike = True
				for mp in doublemetaphone(v.replace('-','').encode('utf8')):
					if mp and mp in idx:
						found |= set(idx[mp])
			elif v in idx:
				found = set(idx[v])
			
			if setCur is None:
				setCur = set(found)
			else:
				setCur &= set(found)
			
			if not setCur:
				if self.debug: print ( "match_indices: match failed. found=", found )
				break
			
			if self.debug: print ( "matched:", setCur )
		
		return FindResult( search, setCur, self, soundalike )
	
	def find( self, search ):
		''' Returns (result, messages) - result will be None if no match. '''
		if self.debug:
			print ( '-' * 60 )
			print ( 'sheet_name:', self.sheet_name )
			print ( 'find: search=', search, hasattr( search, 'last_name'), hasattr( search, 'uci_id' ), getattr( search, 'uci_id' ) )
			print ( self.by_last_name.get('BELHUMEUR', None) )
			print ( self.by_first_name.get('FELIX', None) )

		# First check for a common UCI ID.  If so, attempt to match it exactly and stop.
		if self.useUciId:
			pi = ['by_uci_id']
			if self.has_all_index_fields(search, pi):
				return self.match_indices( search, pi )
		
		# Then check for a common License field.  If so, attempt to match it exactly and stop.
		if self.useLicense:
			pi = ['by_license']
			if self.has_all_index_fields(search, pi):
				return self.match_indices( search, pi )
		
		# If no uci id or license code, try find a perfect, unique match based on the following fields.
		perfectIndices = (
			('by_last_name', 'by_first_name', 'by_nation_code', 'by_age', ),
		)
		for pi in perfectIndices:
			if self.has_all_index_fields(search, pi):
				if self.debug: print ( 'found index:', pi )
				findResult = self.match_indices( search, pi )
				if findResult.get_status() == FindResult.Success:
					return findResult
			
		# Fail-over: try to find a sound-alike on the following combinations.
		indices = []
		if self.soundalike:
			potentialIndices = (
				('by_mp_last_name', 'by_mp_first_name', 'by_nation_code', 'by_age',),
				('by_mp_last_name', 'by_nation_code', 'by_age',),
			)
			
			for pi in potentialIndices:
				if self.has_all_index_fields(search, pi):
					if self.debug: print ( 'found index:', pi )
					indices = pi
					break
		
		if indices:
			return self.match_indices( search, indices )
		
		# Finally, do a special check so to match if there is only first name, last name.
		lastDitchIndices = (
			('by_last_name', 'by_first_name',),
			('by_mp_last_name', 'by_mp_first_name',),
		)
		for pi in lastDitchIndices:
			if not self.soundalike and any(i.startswith('by_mp_') for i in pi):
				continue
			if self.has_all_index_fields(search, pi):
				if self.debug: print ( 'matching on fields:', pi )
				findResult = self.match_indices( search, pi )
				if findResult.get_status() != findResult.NoMatch:
					if self.debug: print ( 'success', findResult )
					return findResult
		
		return FindResult( search, [], self, False )
	
class ResultCollection( object ):
	def __init__( self ):
		self.sources = []
		
	def add_source( self, source ):
		self.sources.append( source )
		
if __name__ == '__main__':
	s = Source( 'CallupTest.xlsx', '2014 Result' )
	# errors = s.read( GetExcelReader(self.fname) )
	print ( s.by_mp_last_name )
	sys.exit()
	
	#for r in s.results:
	#	print ( r )
	for k, v in sorted( ((k, v) for k, v in s.by_mp_last_name.items()), key=operator.itemgetter(0) ):
		print ( '{}: {}'.format(k, ', '.join( Utils.removeDiacritic(r.full_name) for r in v )) )
	for k, v in sorted( ((k, v) for k, v in s.by_mp_first_name.items()), key=operator.itemgetter(0) ):
		print ( '{}: {}'.format(k, ', '.join( Utils.removeDiacritic(r.full_name) for r in v )) )
		
	for r in s.results:
		for p_last in doublemetaphone(r.last_name.replace('-','').encode('utf8')):
			if not p_last:
				continue
			p_last_set = s.by_mp_last_name[p_last]
			for p_first in doublemetaphone(r.first_name.replace('-','').encode('utf8')):
				p_first_set = s.by_mp_first_name[p_first]
				p_last_first_set = p_last_set & p_first_set
				if len(p_last_first_set) > 1:
					print ( ', '.join( u'({}, {}, {})'.format(
							Utils.removeDiacritic(rr.full_name), Utils.removeDiacritic(rr.nation_code), rr.age,
						)
						for rr in p_last_first_set ) )

