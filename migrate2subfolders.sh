#!/bin/sh
# Copyright (c) 2020-2020 Wolfram Schneider, https://bbbike.org
#
# migrate2subfolders.sh - migrated already downloaded images to new sub-folders
#
# usage: cd /mnt/mapillary-disk && migrate2subfolders.sh
#


set -e

# create subfolders first
create_subfolder ()
  {
  for j in 20??-*
  do 
  (
    cd $j
    pwd
    mkdir -p $(ls | sed -e 's,Z.*,Z,'|sort -u)
  )
  done
}

# move images to subfolders
move_images ()
{
  for j in 20??-*
  do 
  (
    cd $j
    if ls | grep -q jpg; then
      pwd
      for i in $(ls | grep '\.jpg$' | sed -e 's,Z.*,Z,'| sort -u)
      do
        echo $i
        for k in 0 1 2 3 4 5 6 7 8 9
        do 
          if ls | grep -q "${i}.*$k.jpg"; then 
            printf "."
            mv ${i}_*${k}.jpg $i
          fi
        done
        echo ""
      done
    fi
  )
  done
}

create_subfolder
move_images

#EOF
