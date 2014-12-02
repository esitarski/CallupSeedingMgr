import wx
import wx.lib.masked.numctrl as NC
import  wx.lib.intctrl as IC
from wx.lib.wordwrap import wordwrap
import wx.lib.filebrowsebutton as filebrowse
import sys
import os
import re
import datetime
import traceback
import xlwt
import webbrowser
from optparse import OptionParser
from roundbutton import RoundButton

import Utils
from ReorderableGrid import ReorderableGrid
import Model
import Version
from GetCallups import GetCallups, make_title
from CallupResultsToGrid import CallupResultsToGrid
from CallupResultsToExcel import CallupResultsToExcel
from MakeExampleExcel import MakeExampleExcel

from Version import AppVerName

def ShowSplashScreen():
	bitmap = wx.Bitmap( os.path.join(Utils.getImageFolder(), 'CallupSeedingMgr.png'), wx.BITMAP_TYPE_PNG )
	showSeconds = 2.5
	frame = wx.SplashScreen(bitmap, wx.SPLASH_CENTRE_ON_SCREEN|wx.SPLASH_TIMEOUT, int(showSeconds*1000), None)

class MainWin( wx.Frame ):
	def __init__( self, parent, id = wx.ID_ANY, title='', size=(200,200) ):
		wx.Frame.__init__(self, parent, id, title, size=size)

		self.SetBackgroundColour( wx.Colour(240,240,240) )
		
		self.fname = None
		self.updated = False
		self.firstTime = True
		
		self.filehistory = wx.FileHistory(16)
		self.config = wx.Config(
			appName="CallupSeedingMgr",
			vendorName="Edward.Sitarski@gmail.com",
			style=wx.CONFIG_USE_LOCAL_FILE
		)
		self.filehistory.Load(self.config)
		
		inputBox = wx.StaticBox( self, label=_('Input') )
		inputBoxSizer = wx.StaticBoxSizer( inputBox, wx.VERTICAL )
		self.fileBrowse = filebrowse.FileBrowseButtonWithHistory(
			self,
			labelText=_('Excel File'),
			buttonText=('Browse...'),
			startDirectory=os.path.expanduser('~'),
			fileMask='Excel Spreadsheet (*.xlsx; *.xlsm; *.xls)|*.xlsx; *.xlsml; *.xls',
			size=(400,-1),
			history=lambda: [ self.filehistory.GetHistoryFile(i) for i in xrange(self.filehistory.GetCount()) ],
			changeCallback=self.doChangeCallback,
		)
		inputBoxSizer.Add( self.fileBrowse, 0, flag=wx.EXPAND|wx.ALL, border=4 )
		
		horizontalControlSizer = wx.BoxSizer( wx.HORIZONTAL )
		
		verticalControlSizer = wx.BoxSizer( wx.VERTICAL )
		self.soundalikeCB = wx.CheckBox( self, label=_("Match misspelled names with Sound-Alike") )
		self.soundalikeCB.SetValue( True )
		verticalControlSizer.Add( self.soundalikeCB, flag=wx.ALL, border=4 )
		
		self.callupSeedingRB = wx.RadioBox(
			self,
			style=wx.RA_SPECIFY_COLS,
			majorDimension=1,
			label=_("Sequence"),
			choices=[
				_("Callups: Highest ranked FIRST (Cyclo-cross, MTB)"),
				_("Seeding: Highest ranked LAST (Time Trials)"),
			],
		)
		verticalControlSizer.Add( self.callupSeedingRB, flag=wx.EXPAND|wx.ALL, border=4 )
		verticalControlSizer.Add( wx.StaticText(self, label=_('Riders with no criteria will be sequenced randomly.')), flag=wx.ALL, border=4 )
		
		horizontalControlSizer.Add( verticalControlSizer, flag=wx.EXPAND )
		
		self.updateButton = RoundButton( self, size=(96,96) )
		self.updateButton.SetLabel( _('Update') )
		self.updateButton.SetFontToFitLabel()
		self.updateButton.SetForegroundColour( wx.Colour(0,100,0) )
		self.updateButton.Bind( wx.EVT_BUTTON, self.doUpdate )
		horizontalControlSizer.Add( self.updateButton, flag=wx.ALL, border=4 )
		
		horizontalControlSizer.AddSpacer( 48 )
		
		vs = wx.BoxSizer( wx.VERTICAL )
		self.tutorialButton = wx.Button( self, label=_('Tutorial...') )
		self.tutorialButton.Bind( wx.EVT_BUTTON, self.onTutorial )
		vs.Add( self.tutorialButton, flag=wx.ALL, border=4 )
		branding = wx.HyperlinkCtrl( self, id=wx.ID_ANY, label=u"Powered by CrossMgr", url=u"http://www.sites.google.com/site/crossmgrsoftware/" )
		vs.Add( branding, flag=wx.ALL, border=4 )
		horizontalControlSizer.Add( vs )

		inputBoxSizer.Add( horizontalControlSizer, flag=wx.EXPAND )
		
		self.sourceList = wx.ListCtrl( self, style=wx.LC_REPORT, size=(-1,160) )
		inputBoxSizer.Add( self.sourceList, flag=wx.ALL|wx.EXPAND, border=4 )
		self.sourceList.InsertColumn(0, "Sheet")
		self.sourceList.InsertColumn(1, "Information Found")
		self.sourceList.InsertColumn(2, "Rows", wx.LIST_FORMAT_RIGHT)
		
		instructions = [
			_('Drag-and-Drop the row numbers on the Left to change the sequence.'),
			_('Click on Points or Position cells for details.'),
			_('Orange Cells: Multiple Matches.  Click on the cell to see what you need to fix in the spreadsheet.'),
			_('Yellow Cells: Soundalike Matches.  Click on the cell to validate if the names are matched correctly.'),
		]
		
		self.grid = ReorderableGrid( self )
		self.grid.CreateGrid( 0, 1 )
		self.grid.SetColLabelValue( 0, u'' )
		self.grid.EnableDragRowSize( False )
		self.grid.Bind( wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.onGridCellClick )
			
		outputBox = wx.StaticBox( self, label=_('Output') )
		outputBoxSizer = wx.StaticBoxSizer( outputBox, wx.VERTICAL )
		
		hs = wx.BoxSizer( wx.HORIZONTAL )
		self.excludeUnrankedCB = wx.CheckBox( self, label=_("Exclude riders with no ranking info") )
		hs.Add( self.excludeUnrankedCB, flag=wx.ALL|wx.ALIGN_CENTRE_VERTICAL, border=4 )
		hs.AddSpacer( 24 )
		hs.Add( wx.StaticText(self, label=_("Output:") ), flag=wx.ALL|wx.ALIGN_CENTRE_VERTICAL, border=4 )
		self.topRiders = wx.Choice( self, choices=[_('All Riders'), _('Top 5'), _('Top 10'), _('Top 15'), _('Top 20'), _('Top 25')] )
		self.topRiders.SetSelection( 0 )
		hs.Add( self.topRiders )
		
		outputBoxSizer.Add( hs )
		
		self.saveAsExcel = wx.Button( self, label=_('Save as Excel...') )
		self.saveAsExcel.Bind( wx.EVT_BUTTON, self.doSaveAsExcel )
		outputBoxSizer.Add( self.saveAsExcel, flag=wx.ALL, border=4 )
		
		mainSizer = wx.BoxSizer( wx.VERTICAL )
		mainSizer.Add( inputBoxSizer, flag=wx.EXPAND|wx.ALL, border = 4 )
		for i, instruction in enumerate(instructions):
			flag = wx.LEFT|wx.RIGHT
			if i == len(instructions)-1:
				flag |= wx.BOTTOM
			mainSizer.Add( wx.StaticText(self, label=instruction), flag=flag, border=8 )
		mainSizer.Add( self.grid, 1, flag=wx.EXPAND|wx.ALL, border = 4 )
		mainSizer.Add( outputBoxSizer, flag=wx.EXPAND|wx.ALL, border = 4 )

		self.SetSizer( mainSizer )
		
	def onTutorial( self, event ):
		if not Utils.MessageOKCancel( self, u"\n".join( [
					_("Launch the CallupSeedingMgr Tutorial."),
					_("This open a sample Excel input file created into your home folder."),
					_("This data in this sheet is made-up, although it does include some current rider's names."),
					u"",
					_("It will also open the Tutorial page in your browser.  If you can't see your browser, make sure you bring to the front."),
					u"",
					_("Continue?"),
					] )
				):
			return
		try:
			fname_excel = MakeExampleExcel()
		except Exception as e:
			Utils.MessageOK( self, u'{}\n\n{}\n\n{}'.format(
					u'Problem creating Excel sheet.',
					e,
					_('If the Excel file is open, please close it and try again')
				)
			)
		self.fileBrowse.SetValue( fname_excel )
		self.doUpdate( event )
		webbrowser.open( fname_excel, new = 2, autoraise = True )
		webbrowser.open( os.path.join(Utils.getHtmlDocFolder(), 'Tutorial.html'), new = 2, autoraise = True )
	
	def onGridCellClick( self, event ):
		row = event.GetRow()
		col = event.GetCol()
		iRecord = int( self.grid.GetCellValue(row, self.grid.GetNumberCols()-1) )
		iSource = self.grid.GetNumberCols() - col
		try:
			v = self.callup_results[iRecord][-iSource+1]
		except IndexError:
			return
		
		try:
			status = v.get_status()
		except AttributeError:
			return
		
		if status == v.NoMatch:
			return
		
		message = u'{}\n\n{}:\n{}\n\n{}:\n{}\n\n{}'.format(
			u'{}: "{}"'.format( _('Soundalike match in sheet') if status == v.SuccessSoundalike else
								_('Multiple matches in sheet') if status == v.MultiMatch else
								_('Match Success in sheet') , v.source.sheet_name),
			_('Registration'),
			v.search.as_str(),
			_('Matches'),
			u'\n'.join( u'{} {}: {}'.format(_('Row'), r.row, r.as_str()) for r in v.matches),
			_('Make changes in the Spreadsheet (if necessary), then press "Update" to refresh the screen.'),
		)
		Utils.MessageOK( self, message, _('Soundalike Match') if status == v.SuccessSoundalike else
										_('Multiple Matches') if status == v.MultiMatch else
										_('Match Success') )
	
	def getTopRiders( self ):
		i = self.topRiders.GetSelection()
		return 5 * i if i > 0 else sys.maxint
		
	def getIsCallup( self ):
		return self.callupSeedingRB.GetSelection() == 0
		
	def getIsSoundalike( self ):
		return self.soundalikeCB.GetValue()
		
	def getOuputExcelName( self ):
		fname_base, fname_suffix = os.path.splitext(self.fname)
		fname_excel = '{}_{}{}'.format(fname_base, 'Callups' if self.getIsCallup() else 'Seeding', '.xlsx')
		return fname_excel
	
	def doChangeCallback( self, event ):
		fname = event.GetString()
		if not fname:
			self.setUpdated( False )
			return
		if fname != self.fname:
			self.doUpdate( event )
		
	def setUpdated( self, updated=True ):
		self.updated = updated
		for w in [self.sourceList, self.grid, self.saveAsExcel]:
			w.Enable( updated )
		if not updated:
			self.sourceList.DeleteAllItems()
			Utils.DeleteAllGridRows( self.grid )
		
	def doUpdate( self, event ):
		self.fname = event.GetString() or self.fileBrowse.GetValue()
		
		if not self.fname:
			Utils.MessageOK( self, _('Missing Excel file.  Please select an Excel file.'), _('Missing Excel File') )
			self.setUpdated( False )
			return
		
		try:
			with open(self.fname, 'rb') as f:
				pass
		except Exception as e:
			Utils.MessageOK( self, u'{}:\n\n    {}\n\n{}'.format( _('Cannot Open Excel file'), fname, e), _('Cannot Open Excel File') )
			self.setUpdated( False )
			return
		
		
		self.filehistory.AddFileToHistory( self.fname )
		self.filehistory.Save( self.config )
		
		try:
			self.registration_headers, self.callup_headers, self.callup_results, self.sources = GetCallups(
				self.fname,
				soundalike = self.getIsSoundalike(),
			)
		except Exception as e:
			traceback.print_exc()
			Utils.MessageOK( self, u'{}:\n\n    {}\n\n{}'.format( _('Excel File Error'), self.fname, e), _('Excel File Error') )
			self.setUpdated( False )
			return
		
		self.setUpdated( True )
		
		self.sourceList.DeleteAllItems()
		def insert_source_info( source, add_value_field=True ):
			idx = self.sourceList.InsertStringItem( sys.maxint, source.sheet_name )
			fields = source.get_ordered_fields()
			if add_value_field and source.get_cmp_policy_field():
				fields = [source.get_cmp_policy_field()] + list(fields)
			self.sourceList.SetStringItem( idx, 1, u', '.join( make_title(f) for f in fields ) )
			self.sourceList.SetStringItem( idx, 2, unicode(len(source.results)) )
		
		insert_source_info( self.sources[-1], False )
		for source in self.sources[:-1]:
			insert_source_info( source )
			
		for col in xrange(3):
			self.sourceList.SetColumnWidth( col, wx.LIST_AUTOSIZE )
		self.sourceList.SetColumnWidth( 2, 52 )
		
		self.grid.BeginBatch()
		CallupResultsToGrid(
			self.grid,
			self.registration_headers, self.callup_headers, self.callup_results,
			is_callup=(self.callupSeedingRB.GetSelection() == 0),
			top_riders=self.getTopRiders(),
			exclude_unranked=self.excludeUnrankedCB.GetValue(),
		)
		self.grid.EndBatch()
		self.GetSizer().Layout()
	
	def doSaveAsExcel( self, event ):
		if self.grid.GetNumberRows() == 0:
			return
			
		fname_excel = self.getOuputExcelName()
		if os.path.isfile( fname_excel ):
			if not Utils.MessageOKCancel(
						self,
						u'"{}"\n\n{}'.format(fname_excel, _('File exists.  Replace?')),
						_('Output Excel File Exists'),
					):
				return
		
		user_sequence = [int(self.grid.GetCellValue(row, self.grid.GetNumberCols()-1)) for row in xrange(self.grid.GetNumberRows())]
		user_callup_results = [self.callup_results[i] for i in user_sequence]
		
		try:
			CallupResultsToExcel(
				fname_excel,
				self.registration_headers, self.callup_headers, user_callup_results,
				is_callup=self.getIsCallup(),
				top_riders=self.getTopRiders(),
				exclude_unranked=self.excludeUnrankedCB.GetValue(),
			)
		except Exception as e:
			Utils.MessageOK( self,
				u'{}: "{}"\n\n{}\n\n"{}"'.format(
						_("Write Failed"),
						e,
						_("If you have this file open, close it and try again."),
						fname_excel),
				_("Excel Write Failed."),
				iconMask = wx.ICON_ERROR,
			)
			return
			
		webbrowser.open( fname_excel, new = 2, autoraise = True )

# Set log file location.
dataDir = ''
redirectFileName = ''
			
def MainLoop():
	global dataDir
	global redirectFileName
	
	app = wx.App( False )
	app.SetAppName("CallupSeedingMgr")
	
	parser = OptionParser( usage = "usage: %prog [options]" )
	parser.add_option("-q", "--quiet", action="store_false", dest="verbose", default=True, help='hide splash screen')
	parser.add_option("-r", "--regular", action="store_true", dest="regular", default=False, help='regular size')
	(options, args) = parser.parse_args()

	dataDir = Utils.getHomeDir()
	redirectFileName = os.path.join(dataDir, 'CallupSeedingMgr.log')
	
	if __name__ == '__main__':
		Utils.disable_stdout_buffering()
	else:
		try:
			logSize = os.path.getsize( redirectFileName )
			if logSize > 1000000:
				os.remove( redirectFileName )
		except:
			pass
	
		try:
			app.RedirectStdio( redirectFileName )
		except:
			pass
	
	mainWin = MainWin( None, title=AppVerName, size=(800,600) )
	if not options.regular:
		mainWin.Maximize( True )

	# Set the upper left icon.
	try:
		icon = wx.Icon( os.path.join(Utils.getImageFolder(), 'CallupSeedingMgr.ico'), wx.BITMAP_TYPE_ICO )
		mainWin.SetIcon( icon )
	except:
		pass

	mainWin.Show()
	
	if options.verbose:
		ShowSplashScreen()
	
	# Start processing events.
	app.MainLoop()

if __name__ == '__main__':
	MainLoop()
