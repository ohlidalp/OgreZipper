______________________________ OgreZipper Readme _______________________________

OgreZipper is a tool for artists who create graphics for OGRE engine using
Blender. It collects exported data, edits mesh and material names, runs mesh.xml
through converter and packs everything into zip.

___________________________________ Usage ______________________________________

____________ Command-line args ___________

There are 2 ways to control OgreZipper: through project file and through args.

To use project file, invoke OgreZipper with path to project file as a first
argument. If project file is specified, all other args are ignored.
If project file is not specified, OgreZipper 
accepts args listed below. Note that args provide very little control, 
you can only process one mesh into one zip.

-n / --name      New mesh name. If not specified, original mesh name is kept.
-x / --xml       Path to .mesh.xml file. If unspecified, it's searched in working dir.
-m / --material  Path to .material file. If unspecified, it's searched in working dir.
-z / --zip       Path to zip file. If unspecified, it's set to
                 *CURRENT_DIR*/*MESH_NAME*.zip
-k / --keep      Keeps orig. .mesh.xml and .material files. Prefixes them with orig_*

____________ Project file ___________

OgreZipper reads all processing directives from a text file. This file is
reffered to as project file or just project. Project files are text files
where every line is considered a directive. Lines starting with '#' are
comment lines and they're ignored.
There are 2 types of directives
- Block directives: These define a certain object, such as zip file or mesh.
	Every block directive consists an opening directive and a closing directive.
- Line directives: These specify properties of their parent blocks.
	They are written as "directiveName:value" pairs.

Recognized block directives:

"Zip/EndZip"
	Specifies a zipfile where all processed data will be saved.
	Line subdirectives are:
		"Path" - sets the path of the zipfile. Absolute or relative.
			If unspecified, "meshpacker.zip" is used.
			If two zips have the same path, OgreZipper merges their contents.
	Block subdirectives are:
		"Extra"
		"Mesh"

"Mesh/EndMesh"
	Inserts a mesh into the parent zipfile.
	Line subdirectives:
		"Name" - The target mesh name (without ".mesh" extension). 
			If not specified, the original filename is used.
		"MaterialFilePath" - Path to associated material file.
		"MeshXmlPath" - Path to exported .mesh.xml file.

"Extra/EndExtra"
	Inserts a file in the parent zipfile
	Line subdirectives:
		"SourcePath"
		"TargetPath" - Path inside zip. Default: root directory.

_____________ Modifications _____________

For unnamed game-engine materials, such names are generated (example):
	Material/SOLID/TEX/TextureName.png 
OgreZipper extracts the texture filename (TextureName.png in this example)
and composes new name like this:
	[MeshName]/[TextureName]

Texture paths are modified automatically to fit into zip file.

_____________ Zip file _______________

The resulting zip file has this structure:
- Mesh files (.mesh) are stored in root directory.
- For every mesh, a directory with it's name is created. It contains:
	- Textures used exclusively by the mesh.
	- A material file named "*MESH_NAME*.material" containing the mesh's materials.
- Textures used by more than one mesh are put in a "SharedTextures" directory.

Extra files may be located anywhere, even in special dirs.

____________ Conflicts _______________

When any conflict is detected, OgreZipper stops. This includes:
	If two meshes have same name (set by Name directive)
