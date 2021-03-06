#!/usr/bin/env python
"""
    DataExplore Application based on pandastable.
    Created January 2014
    Copyright (C) Damien Farrell

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 3
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

from __future__ import absolute_import, print_function
import sys
try:
    from tkinter import *
    from tkinter.ttk import *
except:
    from Tkinter import *
    from ttk import *
if (sys.version_info > (3, 0)):
    from tkinter import filedialog, messagebox, simpledialog
else:
    import tkFileDialog as filedialog
    import tkSimpleDialog as simpledialog
    import tkMessageBox as messagebox

import matplotlib
matplotlib.use('TkAgg', warn=False)
import pandas as pd
import re, os, platform, time
from .core import Table
from .data import TableModel
from .prefs import Preferences
from . import images, util, dialogs
from .dialogs import MultipleValDialog
from . import plugin
from .preferences import Prefs

class DataExplore(Frame):
    """Pandastable viewer application"""

    def __init__(self, parent=None, data=None, projfile=None, msgpack=None):
        "Initialize the application."

        self.parent=parent
        if not self.parent:
            Frame.__init__(self)
            self.main=self.master
        else:
            self.main=Toplevel()
            self.master=self.main

        if getattr(sys, 'frozen', False):
            #the application is frozen
            self.modulepath = os.path.dirname(sys.executable)
        else:
            self.modulepath = os.path.dirname(__file__)

        icon = os.path.join(self.modulepath,'dataexplore.gif')
        img = PhotoImage(file=icon)
        self.main.tk.call('wm', 'iconphoto', self.main._w, img)

        # Get platform into a variable
        self.currplatform = platform.system()
        self.setConfigDir()
        if not hasattr(self,'defaultsavedir'):
            self.defaultsavedir = os.getcwd()

        self.style = Style()
        available_themes = self.style.theme_names()
        plf = Table.checkOS()
        if plf == 'linux':
            self.style.theme_use('default')

        self.style.configure("TButton", padding=(3, 3, 3, 3), relief="raised")
        #self.style.configure("TEntry", padding=(3, 3, 3, 3))
        self.main.title('DataExplore')
        self.createMenuBar()
        self.discoverPlugins()
        self.setupGUI()
        self.clipboarddf = None
        self.projopen = False

        opts = {'layout':{'type':'checkbutton','default':'horizontal'}}
        #self.prefs = Prefs('.dataexplore', opts=opts)
        if data != None:
            self.data = data
            self.newProject(data)
        elif projfile != None:
            self.loadProject(projfile)
        elif msgpack != None:
            self.load_msgpack(msgpack)
        else:
            self.newProject()
        self.main.protocol('WM_DELETE_WINDOW',self.quit)
        self.main.lift()
        return

    def setConfigDir(self):
        """Set up config folder"""

        homepath = os.path.join(os.path.expanduser('~'))
        path = '.dataexplore'
        self.configpath = os.path.join(homepath, path)
        self.pluginpath = os.path.join(self.configpath, 'plugins')
        if not os.path.exists(self.configpath):
            os.mkdir(self.configpath)
            os.makedirs(self.pluginpath)
        return

    def setupGUI(self):
        """Add all GUI elements"""

        self.m = PanedWindow(self.main, orient=HORIZONTAL)
        self.m.pack(fill=BOTH,expand=1)
        self.nb = Notebook(self.main)
        self.m.add(self.nb)
        self.setGeometry()
        return

    def createMenuBar(self):
        """Create the menu bar for the application. """

        self.menu=Menu(self.main)
        self.proj_menu={'01New':{'cmd': self.newProject},
                        '02Open':{'cmd': lambda: self.loadProject(asksave=True)},
                        '03Close':{'cmd':self.closeProject},
                        '04Save':{'cmd':self.saveProject},
                        '05Save As':{'cmd':self.saveasProject},
                        '08Quit':{'cmd':self.quit}}
        if self.parent:
            self.proj_menu['08Return to Database']={'cmd':self.return_data}
        self.proj_menu=self.createPulldown(self.menu,self.proj_menu)
        self.menu.add_cascade(label='Project',menu=self.proj_menu['var'])

        self.sheet_menu={'01Add Sheet':{'cmd': lambda: self.addSheet(select=True)},
                         '02Remove Sheet':{'cmd': lambda: self.deleteSheet(ask=True)},
                         '03Copy Sheet':{'cmd':self.copySheet},
                         '04Rename Sheet':{'cmd':self.renameSheet},
                         '05Sheet Description':{'cmd':self.editSheetDescription}
                         }
        self.sheet_menu=self.createPulldown(self.menu,self.sheet_menu)
        self.menu.add_cascade(label='Sheet',menu=self.sheet_menu['var'])

        self.edit_menu={'01Copy Table':{'cmd': self.copyTable},
                        #'02Preferences..':{'cmd':self.preferencesDialog},
                         }
        self.edit_menu = self.createPulldown(self.menu,self.edit_menu)
        self.menu.add_cascade(label='Edit',menu=self.edit_menu['var'])

        self.table_menu={'01Describe Table':{'cmd':self.describe},
                         '02Convert Column Names':{'cmd':lambda: self._call('convertColumnNames')},
                         '03Convert Numeric':{'cmd': lambda: self._call('convertNumeric')},
                         '04Clean Data': {'cmd': lambda: self._call('cleanData')},
                         '05Correlation Matrix':{'cmd': lambda: self._call('corrMatrix')},
                         '06Concatenate Tables':{'cmd':self.concat},
                         '07Table to Text':{'cmd': lambda: self._call('showasText')},
                         '08Table Info':{'cmd': lambda: self._call('showInfo')} }
        self.table_menu=self.createPulldown(self.menu,self.table_menu)
        self.menu.add_cascade(label='Table',menu=self.table_menu['var'])

        self.dataset_menu={'01Sample Data':{'cmd':self.sampleData},
                         '03Iris Data':{'cmd': lambda: self.getData('iris.csv')},
                         '03Tips Data':{'cmd': lambda: self.getData('tips.csv')},
                         '04Stacked Data':{'cmd':self.getStackedData},
                         '05Pima Diabetes':
                             {'cmd': lambda: self.getData('pima.csv')},
                         '06Titanic':
                             {'cmd': lambda: self.getData('titanic3.csv')},
                         '07miRNA expression':
                             {'cmd': lambda: self.getData('miRNA.csv')},
                         '08CO2 time series':
                             {'cmd': lambda: self.getData('co2-ppm-mauna-loa.csv')}
                         }
        self.dataset_menu=self.createPulldown(self.menu,self.dataset_menu)
        self.menu.add_cascade(label='Datasets',menu=self.dataset_menu['var'])

        self.plots_menu={'01Add plot':{'cmd':self.addPlot},
                         '02Clear plots':{'cmd':self.updatePlotsMenu},
                         '03Plots to pdf':{'cmd':self.pdfReport},
                         '04sep':''}
        self.plots_menu=self.createPulldown(self.menu,self.plots_menu)
        self.menu.add_cascade(label='Plots',menu=self.plots_menu['var'])

        self.plugin_menu={'01Update Plugins':{'cmd':self.discoverPlugins},
                          '02Install Plugin':{'cmd':self.installPlugin},
                          '03sep':''}
        self.plugin_menu=self.createPulldown(self.menu,self.plugin_menu)
        self.menu.add_cascade(label='Plugins',menu=self.plugin_menu['var'])

        self.help_menu={'01Online Help':{'cmd':self.online_documentation},
                        '02About':{'cmd':self.about}}
        self.help_menu=self.createPulldown(self.menu,self.help_menu)
        self.menu.add_cascade(label='Help',menu=self.help_menu['var'])

        self.main.config(menu=self.menu)
        return

    def getBestGeometry(self):
        """Calculate optimal geometry from screen size"""

        ws = self.main.winfo_screenwidth()
        hs = self.main.winfo_screenheight()
        self.w = w = ws/1.4; h = hs*0.7
        x = (ws/2)-(w/2); y = (hs/2)-(h/2)
        g = '%dx%d+%d+%d' % (w,h,x,y)
        return g

    def setGeometry(self):
        self.winsize = self.getBestGeometry()
        self.main.geometry(self.winsize)
        return

    def createPulldown(self,menu,dict):
        """Create pulldown menu"""

        var = Menu(menu,tearoff=0)
        items = list(dict.keys())
        items.sort()
        for item in items:
            if item[-3:] == 'sep':
                var.add_separator()
            else:
                command = None
                if 'cmd' in dict[item]:
                    command = dict[item]['cmd']
                if 'sc' in dict[item]:
                    var.add_command(label='%-25s %9s' %(item[2:],dict[item]['sc']),
                                    command=command)
                else:
                    var.add_command(label='%-25s' %(item[2:]), command=command)
        dict['var'] = var
        return dict

    def progressDialog(self):

        t = Toplevel(self)
        pb = Progressbar(t, mode="indeterminate")
        pb.pack(side="bottom", fill=X)
        t.title('Progress')
        t.transient(self)
        t.grab_set()
        t.resizable(width=False, height=False)
        return pb

    def preferencesDialog(self):
        """Prefs dialog from config parser info"""

        def save():
            d = dialogs.getDictfromTkVars(opts, tkvars, widgets)
            p.writeConfig(d)
        from . import plotting
        defaultfont = 'monospace'
        p=Prefs('.dataexplore')
        opts = {'layout':{'type':'checkbutton','default':False,'label':'vertical plot tools'},
            'fontsize':{'type':'scale','default':12,'range':(5,40),'interval':1,'label':'font size'},
            'colormap':{'type':'combobox','default':'Spectral','items':plotting.colormaps},
                }
        sections = {'main':['layout'],'plot':['fontsize','colormap']}
        p.createConfig(opts)
        t=Toplevel(self)
        dialog, tkvars, widgets = dialogs.dialogFromOptions(t, opts, sections)
        dialog.pack(side=TOP,fill=BOTH)
        bf=Frame(t)
        bf.pack()
        Button(bf, text='Save',  command=save).pack(side=LEFT)
        Button(bf, text='Close',  command=t.destroy).pack(side=LEFT)
        t.title('About')
        t.transient(self)
        t.grab_set()
        t.resizable(width=False, height=False)

        d = dialogs.getDictfromTkVars(opts, tkvars, widgets)
        print (d)
        return

    def loadMeta(self, table, meta):
        """Load meta data for a sheet, this includes plot options and
        table selections"""

        tablesettings = meta['table']
        rowheadersettings = meta['rowheader']

        if 'childtable' in meta:
            childtable = meta['childtable']
            childsettings = meta['childselected']
        else:
            childtable = None
        #load plot options
        opts = {'mplopts': table.pf.mplopts,
                'mplopts3d': table.pf.mplopts3d,
                'labelopts': table.pf.labelopts,
                'layoutopts': table.pf.layoutopts}
        for m in opts:
            if m in meta:
                util.setAttributes(opts[m], meta[m])
                opts[m].updateFromOptions()

        #load table settings
        util.setAttributes(table, tablesettings)
        util.setAttributes(table.rowheader, rowheadersettings)
        if childtable is not None:
            table.createChildTable(df=childtable)
            util.setAttributes(table.child, childsettings)

        #redraw col selections
        if type(table.multiplecollist) is tuple:
            table.multiplecollist = list(table.multiplecollist)
        table.drawMultipleCols()
        return

    def saveMeta(self, table):
        """Save meta data such as current plot options"""

        meta = {}
        #save plot options
        meta['mplopts'] = util.getAttributes(table.pf.mplopts)
        meta['mplopts3d'] = util.getAttributes(table.pf.mplopts3d)
        meta['labelopts'] = util.getAttributes(table.pf.labelopts)
        meta['layoutopts'] = util.getAttributes(table.pf.layoutopts)

        #save table selections
        meta['table'] = util.getAttributes(table)
        meta['rowheader'] = util.getAttributes(table.rowheader)
        #save child table if present
        if table.child != None:
            meta['childtable'] = table.child.model.df
            meta['childselected'] = util.getAttributes(table.child)

        return meta

    def newProject(self, data=None, df=None):
        """Create a new project from data or empty"""

        w = self.closeProject()
        if w == None:
            return
        self.sheets = {}
        self.sheetframes = {} #store references to enclosing widgets
        self.openplugins = {} #refs to running plugins
        self.updatePlotsMenu()
        for n in self.nb.tabs():
            self.nb.forget(n)
        if data != None:
            for s in sorted(data.keys()):
                if s == 'meta':
                    continue
                df = data[s]['table']
                if 'meta' in data[s]:
                    meta = data[s]['meta']
                else:
                    meta=None
                #try:
                self.addSheet(s, df, meta)
                '''except Exception as e:
                    print ('error reading in options?')
                    print (e)'''
        else:
            self.addSheet('sheet1')
        self.filename = None
        self.projopen = True
        self.main.title('DataExplore')
        return

    def loadProject(self, filename=None, asksave=False):
        """Open project file"""

        w=True
        if asksave == True:
            w = self.closeProject()
        if w == None:
            return
        if filename == None:
            filename = filedialog.askopenfilename(defaultextension='.dexpl"',
                                                    initialdir=os.getcwd(),
                                                    filetypes=[("project","*.dexpl"),
                                                               ("All files","*.*")],
                                                    parent=self.main)
        if not filename:
            return
        if os.path.isfile(filename):
            #pb = self.progressDialog()
            #t = threading.Thread()
            #t.__init__(target=pd.read_msgpack, args=(filename))
            #t.start()
            data = pd.read_msgpack(filename)
        else:
            print ('no such file')
            data=None
        self.newProject(data)
        self.filename = filename
        self.main.title('%s - DataExplore' %filename)
        self.projopen = True
        return

    def saveProject(self, filename=None):
        """Save project"""

        if filename != None:
            self.filename = filename
        if not hasattr(self, 'filename') or self.filename == None:
            self.saveasProject()
        else:
            self.doSaveProject(self.filename)
        return

    def saveasProject(self):
        """Save as a new filename"""

        filename = filedialog.asksaveasfilename(parent=self.main,
                                                defaultextension='.dexpl',
                                                initialdir=self.defaultsavedir,
                                                filetypes=[("project","*.dexpl")])
        if not filename:
            return
        self.filename=filename
        self.doSaveProject(self.filename)
        return

    def doSaveProject(self, filename):
        """Save sheets as dict in msgpack"""

        data={}
        for i in self.sheets:
            table = self.sheets[i]
            data[i] = {}
            data[i]['table'] = table.model.df
            data[i]['meta'] = self.saveMeta(table)
        #try:
        pd.to_msgpack(filename, data, encoding='utf-8')
        #except:
        #    print('SAVE FAILED!!!')
        return

    def closeProject(self):
        """Close"""

        if self.projopen == False:
            w = False
        else:
            w = messagebox.askyesnocancel("Close Project",
                                        "Save this project?",
                                        parent=self.master)
        if w==None:
            return
        elif w==True:
            self.saveProject()
        else:
            pass
        for n in self.nb.tabs():
            self.nb.forget(n)
        self.filename = None
        self.projopen = False
        self.main.title('DataExplore')
        return w

    def load_dataframe(self, df, name=None):
        """Load a DataFrame into a new sheet"""

        if hasattr(self,'sheets'):
            self.addSheet(sheetname=name, df=df)
        else:
            data = {name:{'table':df}}
            self.newProject(data)
        return

    def load_msgpack(self, filename):
        """Load a msgpack file"""

        size = round((os.path.getsize(filename)/1.0485e6),2)
        print (size)
        df = pd.read_msgpack(filename)
        name = os.path.splitext(os.path.basename(filename))[0]
        self.load_dataframe(df, name)
        return

    def load_pickle(self, filename):
        """Load a pickle file"""

        df = pd.read_pickle(filename)
        name = os.path.splitext(os.path.basename(filename))[0]
        self.load_dataframe(df, name)
        return

    def getData(self, name):
        """Get predefined data from dataset folder"""

        filename = os.path.join(self.modulepath, 'datasets', name)
        df = pd.read_csv(filename, index_col=0)
        name = os.path.splitext(os.path.basename(filename))[0]
        self.load_dataframe(df, name)
        return

    def addSheet(self, sheetname=None, df=None, meta=None, select=False):
        """Add a sheet with new or existing data"""

        names = [self.nb.tab(i, "text") for i in self.nb.tabs()]
        def checkName(name):
            if name == '':
                messagebox.showwarning("Whoops", "Name should not be blank.")
                return 0
            if name in names:
                messagebox.showwarning("Name exists", "Sheet name already exists!")
                return 0

        noshts = len(self.nb.tabs())
        if sheetname == None:
            sheetname = simpledialog.askstring("New sheet name?", "Enter sheet name:",
                                                initialvalue='sheet'+str(noshts+1))
        if sheetname == None:
            return
        if checkName(sheetname) == 0:
            return
        #Create the table
        main = PanedWindow(orient=HORIZONTAL)
        self.sheetframes[sheetname] = main
        self.nb.add(main, text=sheetname)
        f1 = Frame(main)
        main.add(f1)
        table = Table(f1, dataframe=df, showtoolbar=1, showstatusbar=1)
        table.show()
        f2 = Frame(main)
        main.add(f2, weight=2)
        #show the plot frame
        pf = table.showPlotViewer(f2, layout='horizontal')
        #load meta data
        if meta != None:
            self.loadMeta(table, meta)
        if table.plotted == 'main':
            table.plotSelected()
        elif table.plotted == 'child' and table.child != None:
            table.child.plotSelected()
        self.saved = 0
        self.currenttable = table
        self.sheets[sheetname] = table

        if select == True:
            ind = self.nb.index('end')-1
            s = self.nb.tabs()[ind]
            self.nb.select(s)
        return sheetname

    def deleteSheet(self, ask=False):
        """Delete a sheet"""

        s = self.nb.index(self.nb.select())
        name = self.nb.tab(s, 'text')
        w=True
        if ask == True:
            w = messagebox.askyesno("Delete Sheet",
                                     "Remove this sheet?",
                                     parent=self.master)
        if w==False:
            return
        self.nb.forget(s)
        del self.sheets[name]
        del self.sheetframes[name]
        return

    def copySheet(self, newname=None):
        """Copy a sheet"""

        currenttable = self.getCurrentTable()
        newdata = currenttable.model.df
        meta = self.saveMeta(currenttable)
        self.addSheet(newname, df=newdata, meta=meta)
        return

    def renameSheet(self):
        """Rename a sheet"""

        s = self.nb.tab(self.nb.select(), 'text')
        newname = simpledialog.askstring("New sheet name?",
                                          "Enter new sheet name:",
                                          initialvalue=s)
        if newname == None:
            return
        self.copySheet(newname)
        self.deleteSheet()
        return

    def editSheetDescription(self):
        """Add some meta data about the sheet"""

        from .dialogs import SimpleEditor
        w = Toplevel(self.main)
        w.grab_set()
        w.transient(self)
        ed = SimpleEditor(w, height=25)
        ed.pack(in_=w, fill=BOTH, expand=Y)
        #ed.text.insert(END, buf.getvalue())
        return

    def getCurrentSheet(self):
        """Get current sheet name"""

        s = self.nb.index(self.nb.select())
        name = self.nb.tab(s, 'text')
        return name

    def getCurrentTable(self):

        s = self.nb.index(self.nb.select())
        name = self.nb.tab(s, 'text')
        table = self.sheets[name]
        return table

    def describe(self):
        """Describe dataframe"""

        table = self.getCurrentTable()
        df = table.model.df
        d = df.describe()
        table.createChildTable(d,index=True)
        return

    def concat(self):
        """Concat 2 tables"""

        vals = list(self.sheets.keys())
        if len(vals)<=1:
            return
        d = MultipleValDialog(title='Concat',
                                initialvalues=(vals,vals),
                                labels=('Table 1','Table 2'),
                                types=('combobox','combobox'),
                                parent = self.master)
        if d.result == None:
            return
        else:
            s1 = d.results[0]
            s2 = d.results[1]
        if s1 == s2:
            return
        df1 = self.sheets[s1].model.df
        df2 = self.sheets[s2].model.df
        m = pd.concat([df1,df2])
        self.addSheet('concat-%s-%s' %(s1,s2),m)
        return

    def sampleData(self):
        """Load sample table"""

        df = TableModel.getSampleData()
        name='sample'
        i=1
        while name in self.sheets:
            name='sample'+str(i)
            i+=1
        self.addSheet(sheetname=name, df=df)
        return

    def getStackedData(self):

        df = TableModel.getStackedData()
        self.addSheet(sheetname='stacked-data', df=df)
        return

    def fileRename(self):
        """Start file renaming util"""

        from .rename import BatchRenameApp
        br = BatchRenameApp(self.master)
        return

    def copyTable(self, subtable=False):
        """Copy current table dataframe"""

        table = self.getCurrentTable()
        table.model.df.to_clipboard()
        return

    def pasteTable(self, subtable=False):
        """Paste copied dataframe into current table"""

        #add warning?
        if self.clipboarddf is None:
            return
        df = self.clipboarddf
        table = self.getCurrentTable()
        if subtable == True:
            table.createChildTable(df)
        else:
            model = TableModel(df)
            table.updateModel(model)
        return

    def discoverPlugins(self):
        """Discover available plugins"""

        if getattr(sys, 'frozen', False):
            #the application is frozen
            apppath = os.path.dirname(sys.executable)
        else:
            apppath = os.path.dirname(os.path.abspath(__file__))
        paths = [apppath,self.configpath]
        pluginpaths = [os.path.join(p, 'plugins') for p in paths]
        #print (pluginpaths)
        failed = plugin.init_plugin_system(pluginpaths)
        self.updatePluginMenu()
        return

    def installPlugin(self):
        """Adds a user supplied .py file to plugin folder"""

        filename = filedialog.askopenfilename(defaultextension='.py"',
                                              initialdir=os.getcwd(),
                                              filetypes=[("python","*.py")],
                                              parent=self.main)
        if filename:
            import shutil
            shtutil.copy(filename, self.pluginpath)
            self.updatePluginMenu()
        return

    def updatePluginMenu(self):
        """Update plugins"""

        self.plugin_menu['var'].delete(3, self.plugin_menu['var'].index(END))
        plgmenu = self.plugin_menu['var']
        #for plg in plugin.get_plugins_instances('gui'):
        for plg in plugin.get_plugins_classes('gui'):
            def func(p, **kwargs):
                def new():
                   self.loadPlugin(p)
                return new
            plgmenu.add_command(label=plg.menuentry,
                               command=func(plg))
        return

    def loadPlugin(self, plugin):
        """Instansiate the plugin and call it's main method"""

        p = plugin()
        #plugin should add itself to the table frame if it's a dialog
        try:
            p.main(parent=self)
        except Exception as e:
            messagebox.showwarning("Plugin error", e,
                                    parent=self)
        name = self.getCurrentSheet()
        #track which plugin is running so the last one is removed?
        self.openplugins[name] = p
        return

    def hidePlot(self):
        name = self.getCurrentSheet()
        pw = self.sheetframes[name]
        pw.forget(1)
        return

    def showPlot(self):
        name = self.getCurrentSheet()
        table = self.sheets[name]
        pw = self.sheetframes[name]
        pw.add(table.pf, weight=2)
        return

    def addPlot(self, ):
        """Store the current plot so it can be re-loaded"""

        import pickle
        from . import plotting
        name = self.getCurrentSheet()
        table = self.sheets[name]
        fig = table.pf.fig
        t = time.strftime("%H:%M:%S")
        label = name+'-'+t
        #dump and reload the figure to get a new object
        p = pickle.dumps(fig)
        fig = pickle.loads(p)
        self.plots[label] = fig

        def func(label):
            fig = self.plots[label]
            win = Toplevel()
            win.title(label)
            plotting.addFigure(win, fig)

        menu = self.plots_menu['var']
        menu.add_command(label=label, command=lambda: func(label))
        return

    def updatePlotsMenu(self, clear=True):
        """Clear stored plots"""

        if clear == True:
            self.plots = {}
        menu = self.plots_menu['var']
        menu.delete(4, menu.index(END))
        return

    def pdfReport(self):
        """"""
        from matplotlib.backends.backend_pdf import PdfPages
        pdf_pages = PdfPages('my-document.pdf')
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        for p in self.plots:
            fig = self.plots[p]
            canvas = FigureCanvasTkAgg(fig, master=self)
            #fig.canvas = canvas
            pdf_pages.savefig(fig)
        pdf_pages.close()

        return

    def _call(self, func):
        """Call a table function from it's string name"""

        table = self.getCurrentTable()
        getattr(table, func)()
        return

    def about(self):
        """About dialog"""

        abwin = Toplevel()
        x,y,w,h = dialogs.getParentGeometry(self.main)
        abwin.geometry('+%d+%d' %(x+w/2-200,y+h/2-200))
        abwin.title('About')
        abwin.transient(self)
        abwin.grab_set()
        abwin.resizable(width=False, height=False)
        logo = images.tableapp_logo()
        label = Label(abwin,image=logo,anchor=CENTER)
        label.image = logo
        label.grid(row=0,column=0,sticky='ew',padx=4,pady=4)
        style = Style()
        style.configure("BW.TLabel", font='arial 11')
        from . import __version__
        pandasver = pd.__version__
        pythonver = platform.python_version()
        mplver = matplotlib.__version__

        text='DataExplore Application\n'\
                +'pandastable version '+__version__+'\n'\
                +'Copyright (C) Damien Farrell 2014-\n'\
                +'This program is free software; you can redistribute it and/or\n'\
                +'modify it under the terms of the GNU General Public License\n'\
                +'as published by the Free Software Foundation; either version 3\n'\
                +'of the License, or (at your option) any later version.\n'\
                +'Using Python v%s\n' %pythonver\
                +'pandas v%s, matplotlib v%s' %(pandasver,mplver)

        row=1
        #for line in text:
        tmp = Label(abwin, text=text, style="BW.TLabel")
        tmp.grid(row=row,column=0,sticky='news',pady=2,padx=4)

        return

    def online_documentation(self,event=None):
        """Open the online documentation"""
        import webbrowser
        link='https://github.com/dmnfarrell/pandastable/wiki'
        webbrowser.open(link,autoraise=1)
        return

    def quit(self):
        self.main.destroy()
        return

class TestApp(Frame):
    """Basic test frame for the table"""
    def __init__(self, parent=None):
        self.parent = parent
        Frame.__init__(self)
        self.main = self.master
        self.main.geometry('600x400+200+100')
        self.main.title('DataExplore Test')
        f = Frame(self.main)
        f.pack(fill=BOTH,expand=1)
        df = TableModel.getSampleData()
        self.table = pt = Table(f, dataframe=df,
                                showtoolbar=True, showstatusbar=True)
        pt.show()
        return

def main():
    "Run the application"
    import sys, os
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-f", "--file", dest="msgpack",
                        help="Open a dataframe as msgpack", metavar="FILE")
    parser.add_option("-p", "--project", dest="projfile",
                        help="Open a dataexplore project file", metavar="FILE")
    parser.add_option("-i", "--csv", dest="csv",
                        help="Open a csv file by trying to import it", metavar="FILE")
    parser.add_option("-t", "--test", dest="test",  action="store_true",
                        default=False, help="Run a basic test app")

    opts, remainder = parser.parse_args()
    if opts.test == True:
        app = TestApp()
    else:
        if opts.projfile != None:
            app = DataExplore(projfile=opts.projfile)
        elif opts.msgpack != None:
            app = DataExplore(msgpack=opts.msgpack)
        elif opts.csv != None:
            app = DataExplore()
            t = app.getCurrentTable()
            t.importCSV(opts.csv)
        else:
            app = DataExplore()
    app.mainloop()
    return

if __name__ == '__main__':
    main()
