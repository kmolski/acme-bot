# Commands reference

The following documentation is also available through the `help` command.

Parameter notation follows the manpage conventions - angle brackets indicate
required parameters, while square brackets indicate optional ones. Names of
variable argument lists are followed by three dots.

For example:
**command &lt;required&gt; [optional] [variable_list...]**

ShellModule
-----------

Shell utility commands.

### concat/conc/cat [arguments...]
```
Concatenate all argument strings.

ARGUMENTS
    arguments... - input strings

RETURN VALUE
    The arguments joined into a single string.
```

### count/wc &lt;data&gt;
```
Count lines in the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The number of lines in the input data as an integer.
```

### enumerate/enum/nl &lt;data&gt;
```
Number lines of the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The numbered lines of the input data as a string.
```

### grep &lt;data&gt; &lt;patterns&gt; [opts...]
```
Select lines of the input string that match the given patterns.

ARGUMENTS
    data     - input string
    patterns - regex patterns to match
    opts...  - additional options:
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

### head &lt;data&gt; [line\_count=10]
```
Show the initial lines of the input string.

ARGUMENTS
    data       - input string
    line_count - number of initial lines to display (default: 10)

RETURN VALUE
    The first [line_count] lines of input data as a string.
```

### lines &lt;data&gt; &lt;start&gt; &lt;end&gt;
```
Show the given line range of the input string.

ARGUMENTS
    data  - input string
    start - number of the first line to display
    end   - number of the last line to display

RETURN VALUE
    The selected input data lines as a string.
```

### open &lt;file\_name&gt;
```
Read the contents of a file with the given name.

ARGUMENTS
    file_name - name of the file to read

RETURN VALUE
    The contents of the file as a string.
```

### ping
```
Measure latency between the bot and Discord servers.

RETURN VALUE
    The millisecond latency as an integer.
```

### print &lt;content&gt; [file\_format]
```
Pretty print the input string with the given syntax highlighting.

ARGUMENTS
    content     - input string
    file_format - format for syntax highlighting (default: none)

RETURN VALUE
    The unchanged input data as a string.
```

### shuffle/shuf &lt;data&gt;
```
Randomly shuffle lines of the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The shuffled lines of the input data as a string.
```

### sort &lt;data&gt;
```
Sort lines of the input string alphabetically.

ARGUMENTS
    data - input string

RETURN VALUE
    The sorted lines of the input data as a string.
```

### tail &lt;data&gt; [line\_count=10]
```
Show the final lines of the input string.

ARGUMENTS
    data       - input string
    line_count - number of final lines to display (default: 10)

RETURN VALUE
    The last [line_count] lines of input data as a string.
```

### to-file/tfil/tee &lt;content&gt; &lt;file\_name&gt;
```
Redirect the input string to a file with the given name.

The output file name will be prefixed with your username.

ARGUMENTS
    content   - input string
    file_name - name of the file to write into

RETURN VALUE
    The unchanged input data as a string.
```

### unique/uniq &lt;data&gt;
```
Remove adjacent matching lines from the input string.

ARGUMENTS
    data - input string

RETURN VALUE
    The unique lines of the input data as a string.
```

### units &lt;from\_unit&gt; &lt;to\_unit&gt;
```
Convert between measurement units.

ARGUMENTS
    from_unit - the input expression or measurement unit
    to_unit   - the output measurement unit

RETURN VALUE
    The conversion result as a string.
```

MusicModule
-----------

Music player commands.

### clear
```
Delete all tracks from the queue.

RETURN VALUE
    The removed track URLs as a string.
```

### current/curr
```
Show information about the current track.

RETURN VALUE
    The current track URL as a string.
```

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

### list-urls/lurl [urls...]
```
Extract track URLs from the given playlists.

ARGUMENTS
    urls... - playlist URLs to extract tracks from

RETURN VALUE
    The extracted track URLs as a string.
```

### loop &lt;do\_loop&gt;
```
Set the looping behaviour of the player.

ARGUMENTS
    do_loop - whether to loop after playing all tracks

RETURN VALUE
    The loop parameter as a boolean.
```

### pause
```
Pause the player.
```

### play [query...]
```
Search for and play a track from YouTube.

ARGUMENTS
    query... - the search query

RETURN VALUE
    The added track URL as a string.
```

### play-snd/psnd [query...]
```
Search for and play a track from Soundcloud.

ARGUMENTS
    query... - the search query

RETURN VALUE
    The added track URL as a string.
```

### play-url/purl [urls...]
```
Play YouTube/Soundcloud tracks from the given URLs.

ARGUMENTS
    urls... - track URLs to play

RETURN VALUE
    The added track URLs as a string.
```

### previous/prev [offset=1]
```
Go back the given number of tracks.

ARGUMENTS
    offset - number of tracks to rewind (default: 1)
```

### queue
```
Show all tracks from the current queue.

RETURN VALUE
    The track URLs as a string.
```

### remove/remo &lt;offset&gt;
```
Remove a track from the queue.

ARGUMENTS
    offset - offset of the track to remove

RETURN VALUE
    The removed track URL as a string.
```

### resume/resu
```
Resume playing the current track.
```

### skip/next [offset=1]
```
Skip the given number of tracks.

ARGUMENTS
    offset - number of tracks to skip (default: 1)
```

### stop
```
Stop playing the current track.
```

### volume/volu &lt;volume&gt;
```
Change the current player volume.

ARGUMENTS
    volume - the volume value (from 0 to 100)

RETURN VALUE
    The new volume value as an integer.
```

VersionInfoModule
-----------------

Version &amp; license information commands.

### version/vers
```
Show the version & license information for this instance.

RETURN VALUE
    The version number as a string.
```

