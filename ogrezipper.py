# -*- coding: utf-8 -*-

"""
________________________________________________________________________________

 Ogre zipper script

 This script collects files exported from blender using OgreXMLExporter,
 edits mesh names, material names and texture paths,
 runs xml through OgreXMLConverter
 and zips everything into an archive.

 Original .material and .mesh.xml files are renamed - prefixed with "orig_".
 Unless the "--keep" arg is given, they're deleted when done.

________________________________________________________________________________

 Copyright (C) 2009-2011 Petr Ohlidal

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
________________________________________________________________________________

"""

__author__ = 'Petr Ohlidal'
__version__ = '1.0'
__url__ = 'no webpage yet'
__email__ = 'An00biS@An00biS.cz'


import os
import os.path
import io
import subprocess
import zipfile
import sys
from xml.dom import minidom as dom
import re

# ==== Setup ====

OGREXMLCONVERTER_COMMAND = "OgreXMLConverter"
SHARED_TEXTURES_DIR_NAME = "SharedTextures"

silentMode = False;
def echo(text):
	if not silentMode:
		print(text);

def printVersion():
	print("OgreZipper "+__version__+" ("+__url__+")\nwritten by "+__author__+" <"+__email__+">")

def printHelp():
	printVersion();
	print("\n"
		+"~~~~~~ Usage ~~~~~~\n"
		+"ogrezipper path_to_project_file \n\tGets commands from text file. See README for details.\n"
		+"ogrezipper [args] \n\tParses specified data. Files not specified are searched in current dir.\n"
		+"~~~~ Arguments ~~~~\n"
		+"-v  --version        Prints version and exits.\n"
		+"-h  --help           Prints help and exits\n"
		+"-n  --name           New name for the mesh. If unspecified, original name is kept.\n"
		+"-x  --xml            Path to .mesh.xml file. If unspecified, it's searched in working dir.\n"
		+"-m  --material       Path to .material file. If unspecified, it's searched in working dir.\n"
		+"-z  --zip            Path to zip file. If unspecified, it's set to *CURRENT_DIR*/*MESH_NAME*.zip\n"
		+"-k  --keep           Keeps orig. .mesh.xml and .material files. Prefixes them with orig_*");


"""
Blender generates material names such as: BaseMat/SOLID/TEX/my_texture.png
This function strips the texture name from mat name and returns:
[meshName]/[textureName]
"""
def fixGeneratedMatName( meshName, genMatName ):
	return meshName+"/"+(os.path.split(genMatName.strip())[1]);

def prefixFileName( path, prefix ):
	dirname, filename = os.path.split(path);
	return dirname+prefix+filename;

# ==== Classes ====
class Stack:
	def __init__(self):
		self.stack = []

	def getTop(self):
		if len(self.stack):
			return self.stack[len(self.stack)-1]
		else:
			return ""

	def pop(self):
		return self.stack.pop()

	def push(self, item):
		self.stack.append(item)

"""
Used by ProjectFileParser, represents a target zip file and lists meshes
and extra files to be added into it.
"""
class ProjectZip:
	def __init__(self, path):
		self.meshes = set();
		self.extras = set();
		# This must be an absolute path
		self.path = path;
		# Absolute paths of shared texture files.
		self.sharedTextures = set()

	def isEmpty(self):
		return (self.meshes.size()==0 and self.extras.size()==0)

	def addMesh(self, projectMesh):
		self.meshes.add(projectMesh)

	def setPath(self, path):
		self.path = path

	def getExtras(self):
		return self.extras
	"""
	Validates data, fills/computes missing fields
	Returns True if this object contains enough valid data to be further processed,
	or False if it's badly formed and has to be discarded.
	"""
	def finalize(self):
		if self.path is "":
			echo("Warning: discarding Zip record because it has invalid path.")
			return False
		for mesh in self.meshes:
			if not mesh.finalize():
				self.meshes.remove(mesh)
		for extra in self.extras:
			if not extra.finalize():
				self.extras.remove(extra)
		if len(self.meshes) is 0 and len(self.extras) is 0:
			echo("Warning: discarding Zip record because it's empty")
			return False
		return True

	def merge(self, anotherZip):
		self.extras = self.extras + anotherZip.getExtras()
		self.meshes = self.meshes + anotherZip.getMeshes()

	def getMeshes(self):
		return self.meshes

	def getExtras(self):
		return self.extras

	def getPath(self):
		return self.path

	def addSharedTexture(self, path):
		self.sharedTextures.add(path)

	def isSharedTexture(self, path):
		return path in self.sharedTextures

	def getSharedTextures(self):
		return self.sharedTextures

class ProjectMesh:
	def __init__(self):
		self.name = ""
		self.meshXmlPath = ""
		self.materialPath = ""
		#self.meshPath = ""
		self.texturePaths = set()

	def addTexturePath(self, texturePath):
		self.texturePaths.add(texturePath)

	def setMeshXmlPath(self, meshXmlPath):
		self.meshXmlPath = meshXmlPath

	def getMeshXmlPath(self):
		return self.meshXmlPath

	def setMaterialFilePath(self, matFilePath):
		self.materialPath = matFilePath

	def getMaterialFilePath(self):
		return self.materialPath

	def setName(self,  name):
		self.name = name

	def getName(self):
		return self.name
	"""
	Validates data, fills/computes missing fields
	Returns True if this object contains enough valid data to be further processed,
	or False if it's badly formed and has to be discarded.
	"""
	def finalize(self):
		if len(self.meshXmlPath) is 0 or len(self.materialPath) is 0:
			echo("Warning: Discarding mesh record '"+self.name
				+"' because .mesh.xml file path or .material file path is not set.")
			return False
		if len(self.name) is 0:
			# Set name as mesh.xml file name without the xml extension
			self.name = os.path.basename(self.meshXmlPath)[0:  len(self.meshXmlPath)-5]
		return True

class ProjectExtra:
	def __init__(self):
		self.sourcePath = ""
		self.targetPath = ""

	def setSourcePath(self, path):
		self.sourcePath = path

	def setTargetPath(self, path):
		self.targetPath = path

	def getSourcePath(self):
		return self.sourcePath

	def getTargetPath(self):
		return self.targetPath

	"""
	Validates data, fills/computes missing fields
	Returns True if this object contains enough valid data to be further processed,
	or False if it's badly formed and has to be discarded.
	"""
	def finalize(self):
		if len(self.sourcePath) is 0:
			echo("Warning: Discarding extra-file record because it has no source path.")
			return False
		if self.targetPath is "":
			self.targetPath = os.path.split(self.sourcePath)[1]
		return True


"""
Parses the project file into list of ProjectZip files.
"""
class ProjectFileParser:
	def __init__(self):
		# Objects currently being edited
		# Non-None values flag that a corresponding block is being read.
		self.currentMesh = None
		self.currentZip = None
		self.currentExtra = None
		self.lineIndex = 0
		# HashSet of zipfiles - absolute path is the key.
		self.zipList = dict()
		# Directory where the project file resides - needed for relative paths
		self.basePath = ""

	"""
	Parses entered project file.
	"projectPath" arg must be an absolute path.
	Returns True if all went ok, False on error.
	"""
	def parse(self, projectPath):
		self.lineIndex=0
		self.basePath = os.path.split(projectPath)[0]
		prStream = io.open(projectPath)
		for line in prStream.readlines():
			self.lineIndex=self.lineIndex+1
			line=line.strip()
			if len(line) is 0:
				continue
			if line[0] == '#':
				continue
			# No blocks being read
			if self.currentZip is None:
				if "Zip" in line:
					self.currentZip = ProjectZip("meshpacker.zip")
			# A Zip block being read, no Mesh or Extra blocks opened
			elif self.currentMesh is None and self.currentExtra is None:
				if "EndZip" in line:
					self.flushCurrentZip()
				elif "Mesh" in line:
					self.currentMesh = ProjectMesh()
				elif  "Extra" in line:
					self.currentExtra = ProjectExtra()
				elif  "Path" in line:
					self.currentZip.setPath(self.parsePathDirective(line))
			# A Mesh block being read
			elif self.currentMesh is not None:
				if "EndMesh" in line:
					self.flushCurrentMesh()
				elif  "Name" in line:
					self.currentMesh.setName(self.parseDirectiveValue(line))
				elif  "MaterialFilePath" in line:
					self.currentMesh.setMaterialFilePath(self.parseDirectiveValue(line))
				elif  "MeshXmlPath" in line:
					self.currentMesh.setMeshXmlPath(self.parseDirectiveValue(line))
			# An Extra block being read
			elif self.currentExtra is not None:
				if "EndExtra" in line:
					self.flushCurrentExtra()
				elif  "SourcePath" in line:
					self.currentExtra.setSourcePath(self.parseDirectiveValue(line))
				elif  "TargetPath" in line:
					self.currentExtra.setTargetPath(self.parseDirectiveValue(line))
			else:
				self.printError("Unexpected line "+line
					+" (Directive not valid in this context)")
				return False
		prStream.close()
		return True

	def printError(self, message):
		echo("ERROR parsing project file '"+projectFilePath+"' at line "+str(self.lineIndex+1)+": \n\t"+message)

	def flushCurrentZip(self):
		# Add the zipfile to list
		# If it already exists, merge it.

		if self.currentZip.getPath() in self.zipList:
			self.zipList[self.currentZip.getPath()].merge(self.currentZip)
		else:
			self.zipList[self.currentZip.getPath()] =self.currentZip
		self.currentZip = None

	def flushCurrentMesh(self):
		self.currentZip.addMesh(self.currentMesh)
		self.currentMesh = None

	def flushCurrentExtra(self):
		self.currentZip.addExtra(self.currentExtra)
		self.currentExtra = None

	def parseDirectiveValue(self, line):
		if ':' in line:
			line = line.strip()
			return line[line.rfind(' ')+1:]
		else:
			self.printError("Can't parse directive - missing colon")

	""" Parses path value and converts local path to global """
	def parsePathDirective(self, line):
		path = self.parseDirectiveValue(line)
		if not os.path.isabs(path):
			path = os.path.join(self.basePath, path)
		return path

	def getZipList(self):
		# Finalize entries
		for key, zipFile in self.zipList.items():
			if not zipFile.finalize():
				self.zipList[key] = None;
		return list(self.zipList.values())

# _____________________________________________________________________________
#
#                                  Main
# _____________________________________________________________________________
#

# Global list of zipfiles to create.
# Information is retrieved either from project file or command line args.
zipsToCreate = False

# Handle args
projectFilePath = None;
argMesh = None;
argZip = None;
argKeepOriginals = False;

args = sys.argv[1:]
argIndex = 0
if len(args)>0 and os.path.exists(os.path.join(os.getcwd(), args[0])):
	projectFilePath=args[0]
else:
	while argIndex<len(args):
		arg = args[argIndex];
		# Args without parameters
		if arg in ("-v", "--version"):
			printVersion();
			sys.exit(0);
		if arg in ("-h", "--help"):
			printHelp()
			sys.exit(0)
		if arg in ("-k", "--keep"):
			argKeepOriginals = True
		elif (argIndex+1<len(args)):
			if not argMesh:
				argMesh = ProjectMesh();
			if arg in ("-n", "--name"):
				argMesh.name = argv[argIndex+1];
			if arg in ("-m", "--material"):
				argMesh.materialPath = argv[argIndex+1];
			if arg in ("-x", "--xml"):
				argMesh.meshXmlPath = argv[argIndex+1];
			if arg in ("-z","--zip"):
				argZip = ProjectZip(argv[argIndex+1]);
			argIndex = argIndex+2;
		elif (argIndex==0):
			if (os.path.exists(arg)):

				break;
		else:
			echo("ERROR: Unknown arg: "+arg);
			sys.exit(1);
argIndex = None;
argsLen = None;



if projectFilePath is None:
	zipsToCreate=[]
	# Search for / fill missing values
	if not argMesh:
		argMesh = ProjectMesh();
	if not argMesh.materialPath or not argMesh.meshXmlPath:
		for fileName in os.listdir(os.getcwd()):
			if ".material" in fileName: # TODO use regexp
				if not argMesh.materialPath:
					argMesh.materialPath = fileName;
				else:
					echo("ERROR: Multiple .material files found. Exit.");
					sys.exit(1);
			if ".mesh.xml" in fileName: # TODO use regexp
				if not argMesh.meshXmlPath:
					argMesh.meshXmlPath = fileName;
				else:
					echo("ERROR: Multiple .mesh.xml files found. Exit.");
					sys.exit(1);
		if not argMesh.materialPath:
			echo("ERROR: No material file specified or found. Exit");
			sys.exit(1);
		else:
			echo("Material: "+argMesh.materialPath);
		if not argMesh.meshXmlPath:
			echo("ERROR: No .mesh.xml file specified or found. Exit");
			sys.exit(1);
		else:
			echo("Mesh XML: "+argMesh.meshXmlPath);
	if not argMesh.name:
		meshXmlFileName = os.path.split(argMesh.meshXmlPath)[1];
		argMesh.name = meshXmlFileName[:len(meshXmlFileName)-9];
	echo("Mesh name: "+argMesh.name);
	if not argZip:
		argZip = ProjectZip(argMesh.name+".zip");
	argZip.addMesh(argMesh);
	zipsToCreate.append(argZip);
	argMesh = None;
	argZip = None;
else: # Parse the project file
	parser = ProjectFileParser()
	if not os.path.isabs(projectFilePath):
		projectFilePath = os.path.join(os.getcwd(), projectFilePath)
	parser.parse(projectFilePath)
	zipsToCreate = parser.getZipList()

# Loop zips and work
matPassPattern = re.compile(r'');
for zipInfo in zipsToCreate:
	# Find shared textures
	echo("Looking for shared textures ...")
	allTextures = set()
	for meshInfo in zipInfo.meshes:
#		echo("\t"+meshInfo.getName())
		try:
			matStream = io.open(meshInfo.getMaterialFilePath(), mode='r')
		except IOError:
			echo("ERROR: Can't open "+meshInfo.getMaterialFilePath()+", exit.")
			sys.exit(1)
		texBasePath = os.path.split(meshInfo.getMaterialFilePath())[0]
		texPattern = re.compile(r'texture\s+',  re.I)
		while(True):
			line = matStream.readline()
			if len(line) is 0:
				break
			texMatch = texPattern.search(line)
			if texMatch:
				texPath = line[texMatch.end():]
				texAbsPath = os.path.join(texBasePath, texPath)
				if texAbsPath in allTextures:
					zipInfo.addSharedTexture(texAbsPath)
					echo('\t'+texPath)
				else:
					allTextures.add(texAbsPath)
	texPath = None;
	texAbsPath = None;


	for meshInfo in zipInfo.meshes:

		# Edit the mesh file
		try:
			meshXmlStream = open(meshInfo.meshXmlPath)
		except IOError:
			echo("ERROR: Can't open file "+meshInfo.getMeshXmlPath()+", exit.")
			sys.exit(1)
		meshXmlDoc = dom.parse(meshXmlStream)
		matNodes = meshXmlDoc.getElementsByTagName("submesh")
		for matNode in matNodes:
			if(matNode.hasAttribute("material")):
				matNode.setAttribute("material", fixGeneratedMatName(meshInfo.name, matNode.getAttribute("material")));
		meshXmlStream.close();
		meshXmlStream = open(meshInfo.meshXmlPath, "w");
		meshXmlDoc.writexml(meshXmlStream, encoding="utf-8");
		meshXmlStream.close();
		meshXmlDoc.unlink();
		# If requested, keep orig xml file.
		if argKeepOriginals:
			origMeshXmlPath = prefixFileName(meshInfo.meshXmlPath, "orig_")
			os.rename(meshInfo.meshXmlPath, origMeshXmlPath)


		# Edit the material file
		matStream = io.open(meshInfo.materialPath);
		matOutput = "";
		#sections = Stack();
		texAlphaPass = False;
		twosidedPass = False;
		texBasePath = os.path.split(meshInfo.materialPath)[0]
		insidePass = False;
		insideTextureUnit = False;
		while True:
			# Read line
			matLine = matStream.readline();
			if matLine=="":
				break
			# Process the line
			if "material" in matLine:
				matOutput += "material "+fixGeneratedMatName(meshInfo.name, matLine+'\n');
			elif "pass" in matLine:
				insidePass = True;
				matOutput+=matLine
				continue
			elif "texture_unit" in matLine:
				insideTextureUnit = True;
				matOutput+=matLine
				continue
			# Edit the texture path:
			# Put this mesh's textures to one dir. Put shared textures to "CommonTextures" dir.
			elif "texture" in matLine:
				tabCount = matLine.count('\t');
				lastSpace = matLine.rfind(" ")
				texPath = matLine[lastSpace+1:].strip()
				texAbsPath = os.path.join(texBasePath, texPath)
				matOutput+='\t'*tabCount+"texture "
				if zipInfo.isSharedTexture(texAbsPath):
					matOutput+=SHARED_TEXTURES_DIR_NAME+"/"+texPath+"\n";
				else:
					matOutput+=meshInfo.name+"/"+texPath+'\n';
					meshInfo.addTexturePath(texAbsPath);
				texFileLower = texPath.lower();
				if "alpha" in texFileLower:
					texAlphaPass = True
				if ("twosided" in texFileLower) or ("2sided" in texFileLower):
					twosidedPass = True;
			elif "}" in matLine:
				tabCount = matLine.count("\t")+1;
				echo("} insidePass:" + str(insidePass) + ", insideTextureUnit:" + str(insideTextureUnit));
				if insideTextureUnit:
					insideTextureUnit = False;
				elif insidePass:
					if texAlphaPass:
						matOutput += "\t"*tabCount + "scene_blend alpha_blend\n";
						matOutput += "\t"*tabCount + "depth_write off\n";
						texAlphaPass = False;
					if twosidedPass:
						matOutput += "\t"*tabCount + "cull_hardware none\n";
						twosidedPass = False;
					insidePass = False;
				matOutput+=matLine;
			else:
				matOutput+=matLine
		matStream.close()
		# If requested, keep the orig. mat. file
		if argKeepOriginals:
			origMaterialPath = prefixFileName(meshInfo.materialPath, "orig_")
			os.rename(meshInfo.materialPath, origMaterialPath)
		# Write edited mat. file
		matStream = io.open(meshInfo.materialPath, "wt");
		print("\tMaterial output: "+str(len(matOutput))+" chars");
		matStream.write(matOutput)
		matStream.close();

		# Call OgreXMLConverter
		meshInfo.meshPath = os.path.split(meshInfo.meshXmlPath)[0]+meshInfo.name+".mesh";
		argv = [
				OGREXMLCONVERTER_COMMAND,
				"-q", # Quiet mode
				meshInfo.meshXmlPath, # Source
				meshInfo.meshPath ] # Destination
		echo("Running OgreXMLConverter, argv: \""+str(argv)+"\"");
		res = subprocess.call(argv)
		if res==0:
			echo("\tXML conversion result: "+str(res)+" [OK]");
		else:
			echo("\tXML conversion result: "+str(res)+" [ERROR]");
			sys.exit(1);


	# Create the zip file
	if len(zipInfo.meshes)>0:
		echo("Packing "+zipInfo.path)
		zipStream = zipfile.ZipFile(zipInfo.path,"w",zipfile.ZIP_STORED)
		for meshInfo in zipInfo.meshes:
			echo("\tMesh "+meshInfo.name)
			# Write mesh file
			zipStream.write(meshInfo.meshPath, os.path.basename(meshInfo.meshPath))
			# Write mat file
			zipStream.write(meshInfo.materialPath, meshInfo.name+".material")
			# Write textures (into separate dir)
			for texPath in meshInfo.texturePaths:
				echo ("\t\tTexture: "+texPath)
				zipStream.write(texPath, meshInfo.name+"/"+os.path.basename(texPath))
		for texAbsPath in zipInfo.getSharedTextures():
			zipStream.write(texAbsPath, SHARED_TEXTURES_DIR_NAME+os.path.basename(texAbsPath))
		for extraFile in zipInfo.getExtras():
			zipStream.write(extraFile.getSourcePath(), extraFile.getTargetPath())
		zipStream.close()

# Finished!
echo("Done."); # Phew!
