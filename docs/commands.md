Commands reference
------------------

The following documentation is also available through the `help` bot command.

ShellModule
-----------

Shell utility commands.

### concat/conc/cat
```
Concatenate all argument strings.

ARGUMENTS
    arguments... - input strings

RETURN VALUE
    The arguments joined into a single string.
```

### ping
```
Measure latency between the bot and Discord servers.

RETURN VALUE
    The millisecond latency as an integer.
```

### print
```
Pretty-print the input string with the given syntax highlighting.

ARGUMENTS
    content     - input string
    file_format - name of the language used for syntax highlighting

RETURN VALUE
    The unchanged input data as a string.
```

### to-file/tofi/tee
```
Redirect the input string to a file with the given name.

The output file name will be prefixed with your username.

ARGUMENTS
    content   - input string
    file_name - name of the file to write into

RETURN VALUE
    The unchanged input data as a string.
```

### open
```
Read the contents of a file with the given name.

ARGUMENTS
    file_name - name of the file to read

RETURN VALUE
    The contents of the file as a string.
```

### tts
```
Send the input string as a text-to-speech message.

ARGUMENTS
    content - message content

RETURN VALUE
    The unchanged input data as a string.
```

### grep
```
Select lines of the input string that match the given patterns.

ARGUMENTS
    data     - input string
    patterns - regex patterns to match
    opts     - additional options:
        '-A NUM' - include NUM lines of context following each match
        '-B NUM' - include NUM lines of context preceding each match
        '-C NUM' - include NUM lines of context around each match

        '-E' - interpret `patterns` as extended regular expressions
        '-F' - interpret `patterns` as fixed strings
        '-G' - interpret `patterns` as basic regular expressions

        '-i' - perform case-insensitive matching
        '-o' - only show the matching part of the lines
        '-v' - only show the non-matching input lines
        '-w' - only show matches of whole words
        '-x' - only show exact matches of whole lines

RETURN VALUE
    The selected input data lines as a string.
```

### units
```
Convert between measurement units.

ARGUMENTS
    from_unit - the input expression or measurement unit
    to_unit   - the output measurement unit

RETURN VALUE
    The conversion result as a string.
```

### tail
```
Show the final lines of the input string.

ARGUMENTS
    data       - input string
    line_count - number of final lines to display (default: 10)

RETURN VALUE
    The last [line_count] lines of input data as a string.
```

### head
```
Show the initial lines of the input string.

ARGUMENTS
    data       - input string
    line_count - number of initial lines to display (default: 10)

RETURN VALUE
    The first [line_count] lines of input data as a string.
```

### lines
```
Show the given line range of the input string.

ARGUMENTS
    data  - input string
    start - number of the first line to display
    end   - number of the last line to display

RETURN VALUE
    The selected input data lines as a string.
```

### count/wc
```
Count lines in the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The number of lines in the input data as an integer.
```

### enumerate/enum/nl
```
Number lines of the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The numbered lines of the input data as a string.
```

### sort
```
Sort lines of the input string alphabetically.

ARGUMENTS
    data - input string

RETURN VALUE
    The sorted lines of the input data as a string.
```

### unique/uniq
```
Remove adjacent matching lines from the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The unique lines of the input data as a string.
```

### shuffle/shuf
```
Randomly shuffle lines of the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The shuffled lines of the input data as a string.
```

MusicModule
-----------

Music player commands.

### join
```
Join the sender's current voice channel.
```

### leave
```
Leave the sender's current voice channel.

RETURN VALUE
    The deleted track URLs as a string.
```

### play
```
Search for and play a track from YouTube.

ARGUMENTS
    query... - the search query

RETURN VALUE
    The added track URL as a string.
```

### play-snd/plsn
```
Search for and play a track from Soundcloud.

ARGUMENTS
    query... - the search query

RETURN VALUE
    The added track URL as a string.
```

### play-url/plur
```
Play YouTube/Soundcloud tracks from the given URLs.

ARGUMENTS
    urls... - track URLs to play

RETURN VALUE
    The added track URLs as a string.
```

### list-urls/liur
```
Extract track URLs from the given playlists.

ARGUMENTS
    urls... - playlist URLs to extract tracks from

RETURN VALUE
    The extracted track URLs as a string.
```

### previous/prev
```
Go back the given number of tracks.

ARGUMENTS
    offset - number of tracks to rewind (default: 1)
```

### skip/next
```
Skip the given number of tracks.

ARGUMENTS
    offset - number of tracks to skip (default: 1)
```

### loop
```
Set the looping behaviour of the player.

RETURN VALUE
    The loop parameter as a boolean.
```

### pause
```
Pause the player.
```

### queue
```
Show all tracks from the current queue.

RETURN VALUE
    The track URLs as a string.
```

### resume/resu
```
Resume playing the current track.
```

### clear
```
Delete all tracks from the queue.

RETURN VALUE
    The removed track URLs as a string.
```

### stop
```
Stop playing the current track.
```

### volume/volu
```
Change the current player volume.

ARGUMENTS
    volume - the volume value (from 0 to 100)

RETURN VALUE
    The new volume value as an integer.
```

### current/curr
```
Show information about the current track.

RETURN VALUE
    The current track URL as a string.
```

### remove/remo
```
Remove a track from the queue.

ARGUMENTS
    offset - offset of the track to remove

RETURN VALUE
    The removed track URL as a string.
```

VersionInfoModule
-----------------

Version & license information commands.

### version/vers
```
Show the version & license information for this instance.

RETURN VALUE
    The version number as a string.
```

