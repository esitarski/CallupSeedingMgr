#!/bin/bash

BUILD_CROSSMGR=0
BUILD_CROSSMGRIMPINJ=0
BUILD_TAGREADWRITE=0
OSNAME=$(uname -s)
PYTHONVER=python3.8
ENVDIR=env
LINUXDEPLOY=linuxdeploy-plugin-appimage-x86_64.AppImage
if [ "$OSNAME" == "Darwin" ]; then
	PYTHONVER="python3.7"
fi
if [ "$OSNAME" == "Linux" ]; then
	PYTHONVER="python3.7"
fi

checkEnvActive() {
	if [ -z "$VIRTUAL_ENV" -a -d $ENVDIR ]; then
        . $ENVDIR/bin/activate
        echo "Virtual env ($VIRTUAL_ENV) activated"
    elif [ -n "$VIRTUAL_ENV" ]; then
        echo "Using existing environment ($VIRTUAL_ENV)"
    else
        echo "Python environment not active. Aborting..."
        exit 1
    fi
}

doPyInstaller() {
    checkEnvActive
	ICONPATH=images/
	DISTPATH=dist
	BUILDPATH=build
	case $OSNAME in
		Darwin)	echo pyinstaller ${PROGRAM}.pyw --icon=${ICONPATH}/${PROGRAM}.icns --distpath=$DISTPATH --workpath=$BUILDPATH --clean --windowed --noconfirm --exclude-module=tcl --exclude-module=tk --exclude-module=Tkinter --exclude-module=_tkinter --osx-bundle-identifier=com.esitarsk.crossmgr
			pyinstaller ${PROGRAM}.pyw --icon=${ICONPATH}/${PROGRAM}.icns --distpath=$DISTPATH --workpath=$BUILDPATH --clean --windowed --noconfirm --exclude-module=tcl --exclude-module=tk --exclude-module=Tkinter --exclude-module=_tkinter --osx-bundle-identifier=com.esitarsk.crossmgr
			if [ $? -ne 0 ]; then
				goBack $PROGRAM
				echo "Build Failed!"
				exit 1
			fi
		;;
		Linux) echo pyinstaller ${PROGRAM}.pyw --icon=${ICONPATH}/${PROGRAM}.png --distpath=$DISTPATH --workpath=$BUILDPATH --clean --windowed --noconfirm --exclude-module=tcl --exclude-module=tk --exclude-module=Tkinter --exclude-module=_tkinter --osx-bundle-identifier=com.esitarsk.crossmgr
			pyinstaller ${PROGRAM}.pyw --icon=${ICONPATH}/${PROGRAM}.png --distpath=$DISTPATH --workpath=$BUILDPATH --clean --windowed --noconfirm --exclude-module=tcl --exclude-module=tk --exclude-module=Tkinter --exclude-module=_tkinter --osx-bundle-identifier=com.esitarsk.crossmgr
			if [ $? -ne 0 ]; then
				goBack $PROGRAM
				echo "Build Failed!"
				exit 1
			fi
		;;
		*) echo "Unknown OS."
		exit
		;;
	esac
}

getVersion() {
	if [ ! -f "Version.py" ]; then
		echo "No version file in Version.py. Aborting..."
		exit 1
	fi
	. Version.py
	PROGRAM=$(echo $AppVerName | awk '{print $1}')
	VERSION=$(echo $AppVerName | awk '{print $2}')
	export VERSION
    export PROGRAM
	echo "$PROGRAM Version is $VERSION"
}

cleanup() {
	echo "Cleaning up everything..."
	rm -rf __pycache__ CrossMgrImpinj/__pycache__ TagReadWrite/__pycache__ CrossMgrAlien/__pycache__ SeriesMgr/__pycache__
	rm -rf dist build release
	rm -f *.spec
}

downloadAppImage() {
	if [ "$OSNAME" == "Linux" ];then
		if [ -f $LINUXDEPLOY ]; then
			echo "$LINUXDEPLOY already installed"
		else
			wget -v https://github.com/linuxdeploy/linuxdeploy-plugin-appimage/releases/download/continuous/$LINUXDEPLOY
			chmod 755 $LINUXDEPLOY
		fi
	else
		echo "AppImage builder not requried for $OSNAME"
	fi
}

compileCode() {
    checkEnvActive
	echo "Compiling code"
	python3 -mcompileall -l .
	if [ $? -ne 0 ];then
		echo "Compile failed. Aborting..."
		exit 1
	fi
}

buildLocale() {
	localepath="locale"
	echo $localepath
	locales=$(find $localepath -type d -depth 1)
	for locale in $locales
	do
		pofile="${locale}/LC_MESSAGES/messages.po"
		echo "Building Locale: $locale"
		echo "python -mbabel compile -f -d $localepath -l $locale -i $pofile"
		python -mbabel compile -f -d $localepath -l $locale -i $pofile
		if [ $? -ne 0 ]; then
			echo "Locale $locale failed. Aborting..."
			exit 1
		fi
	done
}

copyAssets(){
	if [ "$OSNAME" == "Darwin" ]; then
		RESOURCEDIR="dist/${PROGRAM}.app/Contents/Resources/"
	else
		RESOURCEDIR="dist/${PROGRAM}/usr/bin/"
	fi
	mkdir -p $RESOURCEDIR
	if [ "$OSNAME" == "Linux" ];then
                mv dist/${PROGRAM}/* $RESOURCEDIR
                cp -v "images/${PROGRAM}.png" "dist/${PROGRAM}"
		echo "Setting up AppImage in dist/${PROGRAM}"
		sed "s/%PROGRAM%/$PROGRAM/g" appimage/AppRun.tmpl > "dist/${PROGRAM}/AppRun"
		chmod 755 "dist/${PROGRAM}/AppRun"
		sed "s/%PROGRAM%/$PROGRAM/g" appimage/template.desktop > "dist/${PROGRAM}/${PROGRAM}.desktop"
	fi
	if [ -d "images" ]; then
		echo "Copying Images to $RESOURCEDIR"
		cp -rv "images" $RESOURCEDIR
	fi
	if [ -d "html" ]; then
		echo "Copying Html to $RESOURCEDIR"
		cp -rv "html" $RESOURCEDIR
	fi
	if [ -d "htmldoc" ]; then
		echo "Copying HtmlDoc to $RESOURCEDIR"
		cp -rv "${PROGRAM}HtmlDoc" $RESOURCEDIR
	fi
	if [ -d "locale" ]; then
		buildLocale $PROGRAM
		echo "Copying Locale to $RESOURCEDIR"
		cp -rv "locale" $RESOURCEDIR
	fi

	if [ -d helptxt  ];then
		if [ -d htmlindex ]
		then
			rm -rf htmlindex
		fi
		echo "Building Help for CrossMgr ..."
		python3 buildhelp.py
		if [ $? -ne 0 ]; then
			echo "Building help failed. Aborting..."
			exit 1
		fi
		cp -rv htmlindex $RESOURCEDIR
	fi
}

package() {
    checkEnvActive

	if [ $OSNAME == "Darwin" ];then
		echo "Packaging MacApp into DMG..."
		echo "dmgbuild -s dmgsetup.py $PROGRAM $PROGRAM.dmg"
		dmgbuild -s dmgsetup.py $PROGRAM $PROGRAM.dmg
		RESULT=$?
		if [ $RESULT -ne 0 ]; then
			echo "Packaging failed. Aborting..."
			exit 1
		fi
	else
		downloadAppImage
		echo "Packaging Linux app to AppImage..."
		export ARCH=x86_64
		./${LINUXDEPLOY} --appdir "dist/${PROGRAM}"
		if [ $? -ne 0 ]; then
			echo "Packaging failed. Aborting..."
			exit 1
		fi
	fi

}

moveRelease() {
	echo "Moving to release directory..."
	if [ -z "$VERSION" ]; then
		getVersion $PROGRAM
	fi
	mkdir -p release
	if [ "$OSNAME" == "Darwin" ]; then
		mv "${PROGRAM}_${VERSION}.dmg" release/
	else
		mv ${PROGRAM}*.AppImage release/
	fi
}

envSetup() {
	if [ ! -f requirements.txt ]; then
		echo "Script must be run in same main directory with requirements.txt. Aborting..."
		exit 1
	fi
	if [ -z "$VIRTUAL_ENV" ]; then
		if [ -d $ENVDIR ]; then
			echo "Activating virtual env ($ENVDIR) ..."
			. env/bin/activate
		else
			echo "Creating virtual env in $ENVDIR..."
			$PYTHONVER -mpip install virtualenv
            if [ $? -ne 0 ];then
                echo "Virtual env setup failed. Aborting..."
                exit 1
            fi
			$PYTHONVER -mvirtualenv $ENVDIR -p $PYTHONVER
            if [ $? -ne 0 ];then
                echo "Virtual env setup failed. Aborting..."
                exit 1
            fi
			. env/bin/activate
		fi
	else
		echo "Already using $VIRTUAL_ENV"
	fi
	pip3 install -r requirements.txt
    if [ $? -ne 0 ];then
        echo "Pip requirememnts install failed. Aborting..."
        exit 1
    fi
    if [ $OSNAME == "Darwin" ];then
		pip3 install dmgbuild
	else
		downloadAppImage
	fi
}

buildall() {
    checkEnvActive
    cleanup
    getVersion
    compileCode
    doPyInstaller
    copyAssets
    package
    moveRelease
}

tagrelease() {
	getVersion "CrossMgr"
	DATETIME=$(date +%Y%m%d%H%M%S)
	TAGNAME="v$VERSION-$DATETIME"
	echo "Tagging with $TAGNAME"
	git tag $TAGNAME
	git push --tags
}

doHelp() {
	cat <<EOF
$0 [ -hcCtaep: ]
 -h        - Help
 -E [env]  - Use Environment ($VIRTUAL_ENV)
 -p [pythonexe]  - Python version (Default $PYTHONVER)

 -d        - Download AppImage builder
 -S        - Setup environment
 -C        - Clean up everything
 -c        - Compile code
 -P        - Run pyinstaller
 -o        - Copy Assets to dist directory
 -k        - Package application
 -m        - Move package to release directory
 -A        - Build everything and package
 -l        - list files in release directory
 -f        - Fix SeriesMgr files

 -T        - Tag for release

Running on: $OSNAME

To setup the build environment after a fresh checkout, use:
$0 -S

To build all the applications and package them, use:
$0 -a -A

EOF
	exit
}

getVersion

gotarg=0
while getopts "hvcp:dSBPZokmAT" option
do
	gotarg=1
	case ${option} in
		h) doHelp
		;;
		v) 
		;;
		C) 	cleanup
		;;
		p) PYTHONVER=$OPTIONARG
		   echo "Using Python: $PYTHONVER"
		;;
		d) downloadAppImage
		;;
		S) envSetup
		;;
		c)  compileCode
		;;
		P)	doPyInstaller
		;;
		Z) buildLocale
		;;
		o) copyAssets
		;;
		k) package
		;;
		m) moveRelease
		;;
		A) buildall
		;;
		z) checkEnvActive
		;;
		T) tagrelease
		;;
		*) doHelp
		;;
	esac
done

if [ $gotarg -eq 0 ]; then
	echo "No arguments given"
	doHelp
	exit 1
fi

