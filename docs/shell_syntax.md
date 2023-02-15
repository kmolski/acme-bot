# Syntax overview

If you've ever used a Unix shell, this syntax will probably look familiar to you.  
The main differences from conventional shells include:
- [Interaction of pipes with arguments](#pipescompositions)
- [Expression/command substitution](#expression-substitution)
- [File content substitution](#file-content-substitution)

Executing commands
------------------

Commands are executed by writing their name followed by any number of arguments:
```
!help play-url
!play-url https://www.youtube.com/watch?v=dQw4w9WgXcQ
!stop

!units "1 millilightsecond" kilometer
```

Arguments can have the following types (matched in this exact order):
- Integers
- Booleans: yes/no, true/false, enable/disable, on/off
- [File content substitutions](#file-content-substitution)
- [Expression substitutions](#expression-substitution)
- Strings
  - single words
  - quoted strings
  - markdown code blocks:
  ````
    !concat "text " ```
    inside a code block
    ```
  ````

Expression substitution
-----------------------

Command outputs can be passed to other commands as arguments.  
The substitution is enclosed in parentheses, as in the example below:
```
# play tracks from files named "gloryhammer.txt" and "rick.txt"
!play-url (open "gloryhammer.txt") (open "rick.txt")

# join the value of 451°F converted to Kelvins with the string " Kelvin"
!concat (units "tempF(451)" K) " Kelvin"
```

In contrast to many Unix shells, there is no expansion - substituted values are always passed as one argument.

File content substitution
-------------------------

The content of any file from the user's current channel can be used as an argument.

The first matching file in the channel will be assigned as the argument value.  
Filenames are enclosed in square brackets, for example:
```
# play tracks from files named "sabadu.txt" and "nanowar.txt"
!play-url [sabadu.txt] [nanowar.txt]

# display lines 450-500 from the file named "code.py"
!lines [code.py] 450 500
```

Sequences
---------

Commands can be executed one after another using the `&&` operator.  
If any expression/command fails, the next ones won't be run.

For example:
```
# remove all tracks and play new tracks from the file named "newlist.txt"
!clear && play-url [newlist.txt]

# disable looping and skip to the next track
!loop off && next
```

Pipes/compositions
------------------

Commands can be chained together using the `|` operator.  
Return values of previous steps are passed as the first argument to the following steps.

For example:
```
# leave the channel and save all tracks to a file called "queue.txt"
# the return value of `leave` is assigned to the `content` argument of `to-file`
!leave | to-file "queue.txt"

# search for the word "eval" in a file named "code.py", then display
# all matches with Python syntax highlighting and line numbers
#
# the return value of `enumerate` is assigned to the `data` argument of `grep`
# the return value of `grep` is assigned to the `content` argument of `print`
!enumerate [code.py] | grep eval | print python
```