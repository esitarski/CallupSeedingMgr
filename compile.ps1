﻿<#	
	.NOTES
	===========================================================================
	 Created with: 	SAPIEN Technologies, Inc., PowerShell Studio 2019 v5.6.170
	 Created on:   	12/26/2019 11:07 AM
	 Created by:   	Mark Buckaway
	 Organization: 	
	 Filename:     	
	===========================================================================
	.DESCRIPTION
		A description of the file.
#>

# Command line options
param (
	[switch]$help = $false,
	[string]$environ = "env",
	[string]$pythonexe = "python3.7.exe",
	[switch]$versioncmd = $false,
	[switch]$setupenv = $false,
	[switch]$clean = $false,
	[switch]$compile = $false,
	[switch]$pyinst = $false,
	[switch]$copyasset = $false,
	[switch]$package = $false,
	[switch]$everything = $false,
	[switch]$tag = $false,
	[switch]$checkver = $false,
	[switch]$locale = $false,
	[switch]$virus = $false
)

# Globals
$environ = "env"
$script:pythongood = $false

# Check the python version. Current only 3.7.x is supported because pyinstaller doesn't work on 3.8
function CheckPythonVersion
{
	if ($script:pythongood -eq $false)
	{
		$pythonver = ' '
		$result = (Start-Process -Wait -NoNewWindow -RedirectStandardOutput 'pyver.txt' -FilePath "python.exe" -ArgumentList "--version")
		if (!(Test-Path 'pyver.txt'))
		{
			Write-Host "Cant find python version. Aborting..."
			exit 1
		}
		$pythonver = Get-Content 'pyver.txt'
		Remove-Item 'pyver.txt'
		$version = $pythonver.Split(' ')[1]
		$minor = $version.Split('.')[1]
		if ($minor -ne '7')
		{
			Write-Host "Python 3.7.x required, and you have ", $version, "installed. Aborting..."
			exit 1
		}
		Write-Host "Found Python ", $version
		$script:pythongood = $true
	}
	
}

function CheckEnvActive
{
	Write-Host $env:VIRTUAL_ENV
	if (([string]::IsNullOrEmpty($env:VIRTUAL_ENV)) -and (Test-Path -Path $environ))
	{
		$runenv = "$environ\scripts\activate.ps1"
		Invoke-Expression $runenv
		Write-Host "Virtual environment ($env:VIRTUAL_ENV) activated"
	}
	elseif (!([string]::IsNullOrEmpty($env:VIRTUAL_ENV)))
	{
		Write-Host "Using existing environment ($env:VIRTUAL_ENV)"
	}
	else
	{
		Write-Host "Python environment not active. Aborting..."
		exit 1		
	}
	
}

function doPyInstaller
{
	CheckPythonVersion
	CheckEnvActive
	($program, $version) = GetVersion
	$iconpath = "images"
	$distpath = "dist"
	$buildpath = "build"
	Write-Host "pyinstaller.exe $program.pyw --icon=$iconpath\$program.ico --distpath=$distpath --workpath=$buildpath --clean --windowed --noconfirm --exclude-module=tcl --exclude-module=tk --exclude-module=Tkinter --exclude-module=_tkinter"
	Start-Process -Wait -NoNewWindow -FilePath "pyinstaller.exe" -ArgumentList "$program.pyw --icon=$iconpath\$program.ico --distpath=$distpath --workpath=$buildpath --clean --windowed --noconfirm --exclude-module=tcl --exclude-module=tk --exclude-module=Tkinter --exclude-module=_tkinter"
	$result = $?
	if ($result -eq $false)
	{
		Write-Host "Build failed. Aborting..."
		exit 1
	}
}

function GetVersion
{
	if (!(Test-Path -Path "Version.py"))
	{
		Write-Host "No version file in Version.py. Aborting..."
		exit 1
	}
	$versionItem = Get-Content "Version.py"
	$versionItem = $versionItem.Split('=')[1].Replace("`"", "")
	$program = $versionItem.Split(' ')[0]
	$version = $versionItem.Split(' ')[1]
	Write-Host $program, "Version is", $version
	return ($program, $version)
}

function Cleanup
{
	Write-Host 'Cleaning up everything...'
	$dirs = @(
		'__pycache__',
		'CrossMgrImpinj/__pycache__',
		'TagReadWrite/__pycache__',
		'CrossMgrAlien/__pycache__',
		'SeriesMgr/__pycache__',
		'dist',
		'build',
		'release',
		'*.spec'
	)
	foreach ($dir in $dirs)
	{
		Write-Host 'Cleaning: ', $dir
		Remove-Item -Recurse -Force -ErrorAction Ignore $dir
	}
}

function CompileCode
{
	CheckPythonVersion
	CheckEnvActive
	Write-Host "Compiling code..."
	Start-Process -Wait -NoNewWindow -FilePath "python.exe" -ArgumentList "-mcompileall -l ."
	if ($? -eq $false)
	{
		Write-Host "Compile failed. Aborting..."
		exit 1
	}
}

function BuildLocale
{
	CheckPythonVersion
	CheckEnvActive
	$localepath = "locale"
	$locales = Get-ChildItem -Directory -Path $localepath
	foreach ($locale in $locales)
	{
		$pofile="$localepath\$locale\LC_MESSAGES\messages.po"
		Write-Host "Building Locale: $locale"
		Write-Host "python -mbabel compile -f -d $localepath -l $locale -i $pofile"
		Start-Process -Wait -NoNewWindow -FilePath "python.exe" -ArgumentList "-mbabel compile -f -d $localepath -l $locale -i $pofile"
		if ($? -eq $false)
		{
			Write-Host "Locale $locale failed. Aborting..."
			exit 1
		}
	}
}

function CopyAssets
{
	($program, $version) = GetVersion
	$resourcedir = "dist/$program"
	if (!(Test-Path -Path $resourcedir))
	{
		New-Item -ItemType Directory -Force $resourcedir
	}
	if (Test-Path "images")
	{
		Write-Host "Copying Images to $resourcedir"
		Copy-Item -Recurse -Force -Path "images" -Destination "$resourcedir"
	}
	if (Test-Path "html")
	{
		Write-Host "Copying Html to $resourcedir"
		Copy-Item -Recurse -Force -Path "html" -Destination "$resourcedir"
	}
	if (Test-Path "htmldoc")
	{
		Write-Host "Copying HtmlDoc to $resourcedir"
		Copy-Item -Recurse -Force -Path "htmldoc" -Destination "$resourcedir"
	}
	if (Test-Path "locale")
	{
		BuildLocale
		Write-Host "Copying Locale to $resourcedir"
		Copy-Item -Recurse -Force -Path "locale" -Destination "$resourcedir"
	}
	if (Test-Path "helptxt")
	{
		
		if (Test-Path "htmlindex")
		{
			Remove-Item -Recurse -Force -Path "htmlindex"
		}
		Write-Host 'Building Help for CrossMgr...'
		Start-Process -Wait -NoNewWindow -FilePath "python.exe" -ArgumentList "buildhelp.py"
		if ($? -eq $false)
		{
			Write-Host "Help Build failed. Aborting..."
			exit 1
		}
		Copy-Item -Recurse -Force -Path "htmlindex" -Destination "$resourcedir"
	}
	
}

function Package
{
	($program, $version) = GetVersion
	$newinstallname = "${program}_Setup_x64_v${version}".Replace('.', '_')
	$yeartoday = (Get-Date).Year
	$curdir = (Get-Item -Path ".\").FullName
	$sourcepath = "$curdir\dist\$program"
	$releasepath = "$curdir\release"
	
	Write-Host "Packaging $program from $sourcepath to $newinstallname in $releasepath..."
	$setup = "AppName=$program
SourceDir=$sourcepath
AppPublisher=Edward Sitarski
AppContact=Edward Sitarski
AppCopyright=Copyright (C) 2004-$yeartoday Edward Sitarski
AppVerName=$program
AppPublisherURL=http://www.sites.google.com/site/crossmgrsoftware/
AppUpdatesURL=http://github.com/estarski/$program/
VersionInfoVersion=$version
VersionInfoCompany=Edward Sitarski
VersionInfoProductName=$program
VersionInfoCopyright=Copyright (C) 2004-$yeartoday Edward Sitarski
OutputBaseFilename=$newinstallname
OutputDir=$releasepath
"
	Set-Content -Path "inno_setup.txt" -Value "$setup"
	# Scan the registry for innosetup 6.x
	$apps=(Get-ChildItem HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | % { Get-ItemProperty $_.PsPath } | Select DisplayName, InstallLocation | Sort-Object Displayname -Descending)
	foreach ($app in $apps)
	{
		if ($app.DisplayName -like 'Inno Setup version 6*')
		{
			$innolocaton = $app.InstallLocation
			break
		}
	}
	if (![string]::IsNullOrEmpty($innolocaton) -and (Test-Path -Path $innolocaton))
	{
		Write-Host "InnoSetup 6 installed $innolocaton (registry)"
	}
	elseif (Test-Path -Path 'C:\Program Files (x86)\Inno Setup 6')
	{
		$innolocaton = 'C:\Program Files (x86)\Inno Setup 6\'
		Write-Host "InnoSetup 6 installed $innolocaton (directory)"
	}
	elseif (Test-Path -Path 'C:\Program Files\Inno Setup 6')
	{
		$innolocaton = 'C:\Program Files\Inno Setup 6\'
		Write-Host "InnoSetup 6 installed $innolocaton (directory)"
	}
	elseif (Test-Path -Path 'D:\Program Files (x86)\Inno Setup 6')
	{
		$innolocaton = 'D:\Program Files (x86)\Inno Setup 6\'
		Write-Host "InnoSetup 6 installed $innolocaton (directory)"
	}
	elseif (Test-Path -Path 'D:\Program Files\Inno Setup 6')
	{
		$innolocaton = 'D:\Program Files\Inno Setup 6\'
		Write-Host "InnoSetup 6 installed $innolocaton (directory)"
	}
	else
	{
		Write-Host "Cant find Inno Setup 6.x! Is it installed? Aborting...."
		exit 1
	}
	$inno = "${innolocaton}ISCC.exe"
	Start-Process -Wait -NoNewWindow -FilePath "$inno" -ArgumentList "${program}.iss"
	if ($? -eq $false)
	{
		Write-Host "Inno Setup failed. Aborting..."
		exit 1
	}
	
}

function EnvSetup
{
	CheckPythonVersion
	if (!(Test-Path -Path 'requirements.txt'))
	{
			Write-Host 'Script must be run from the same directory as the requirements.txt file. Aborting...'
			exit 1
	}
	if ([string]::IsNullOrEmpty($env:VIRTUAL_PATH))
	{
		if (Test-Path -Path $environ)
		{
			Write-Host 'Activing virtual env', $env:VIRTUAL_ENV, '...'
			$runenv = "$environ/scripts/activate.ps1"
			Invoke-Expression $runenv
			if ($? -eq $false)
			{
				Write-Host 'Virtual env activation failed. Aborting...'
				exit 1
			}
		}
		else
		{
			Write-Host "Creating Virtual env", $environ
			Start-Process -Wait -NoNewWindow -FilePath "python.exe" -ArgumentList "-mpip install virtualenv"
			if ($? -eq $false)
			{
				Write-Host 'Virtual env setup failed. Aborting...'
				exit 1
			}
			Start-Process -Wait -NoNewWindow -FilePath "python.exe" -ArgumentList "-mvirtualenv $environ"
			if ($? -eq $false)
			{
				Write-Host 'Virtual env setup failed. Aborting...'
				exit 1
			}
			$runenv = "$environ/scripts/activate.ps1"
			Invoke-Expression $runenv
			if ($? -eq $false)
			{
				Write-Host 'Virtual env activation failed. Aborting...'
				exit 1
			}
		}
	}
	else
	{
		Write-Host 'Already using', $env:VIRTUAL_ENV
	}
	$result = (Start-Process -Wait -NoNewWindow -FilePath "python.exe" -ArgumentList "-mpip install -r requirements.txt")
	if ($? -eq $false)
	{
		Write-Host 'Pip requirements.txt setup failed. Aborting...'
		exit 1
	}
	
}

function BuildAll
{
	CheckPythonVersion
	CheckEnvActive
	Cleanup
	CompileCode
	doPyInstaller
	CopyAssets
	Package
}

function Virustotal
{
	Write-Host "Sending files to VirusTotal..."
	$files = Get-ChildItem -Path "release\*.exe"
	
	foreach ($file in $files)
	{
		Write-Host "Uploading $file to VirusTotal..."
		Start-Process -Wait -NoNewWindow -FilePath "python.exe" -ArgumentList "VirusTotalSubmit.py -v $file"
	}
		
}

function TagRelease
{
	($program, $version) = GetVersion
	$date = Get-Date -format "yyyyMMddHHmmss"
	$tagname = "v$version-$date"
	Write-Host "Tagging with $tagname"
	Start-Process -Wait -NoNewWindow -FilePath "git.exe" -ArgumentList "tag $tagname"
	Start-Process -Wait -NoNewWindow -FilePath "git.exe" -ArgumentList "push --tags"
}

function doHelp
{
	Write-Host '
	compile.ps1 [-help]
	-help              - Help
	-environ [env]     - Use Environment ($env:VIRTUAL_ENV)
	-pythonexe [pythonexe]  - Python version (Default $pythonver)
	
	-checkver     - check python version
	-version      - Get versions
	-setupenv     - Setup environment
	-clean        - Clean up everything
	-compile      - Compile code
	-locale       - Build locale files
	-pyinstall    - Run pyinstaller
	-copy         - Copy Assets to dist directory
	-package      - Package application
	-everything   - Build everything and package
    -virus        - Send releases to VirusTotal
	
	-tag          - Tag for release
	
	To setup the build environment after a fresh checkout, use:
	compile.ps1 -setupenv
	
	To build all the applications and package them, use:
	compile.ps1 -all -everything
	'
	exit 1
}

if ($help -eq $true)
{
	doHelp
}

$programs = @()

if ($tag -eq $true)
{
	tagRelease
	exit 1
}

if ($checkver)
{
	CheckPythonVersion
	exit 1
}

if ($setupenv -eq $true)
{
	EnvSetup
}

if ($clean -eq $true)
{
	Cleanup
}

if ($everything -eq $false)
{
	if ($versioncmd -eq $true)
	{
		($program, $version) = GetVersion
	}
	if ($compile -eq $true)
	{
			CompileCode
	}
	if ($locale -eq $true)
	{
		BuildLocale
	}
	if ($pyinst -eq $true)
	{
		doPyInstaller
	}
	if ($copyasset -eq $true)
	{
		CopyAssets($program)
	}
	if ($package -eq $true)
	{
		Package($program)
	}
}
else
{
	BuildAll($programs)
}
if ($virus -eq $true)
{
	Virustotal
}

