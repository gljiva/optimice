11-08-2012: Removed zip package as it was buggy and fairly behind svn version. So everyone should dload latest svn version to play with.

15-01-2012: \o\... A bit late Christmas present. I see many ppl download zip archive that was pretty old and buggy compared to the svn version, so here is new 0.14 zip package with many fixes, some new optimizations and better stability. Also big thanks to everyone who sent bug reports and improvement ideas: cATa, Andrew, Mikhail, Skier, Marian, Ralf, Alex...

18-07-2011: \o/ code is in SVN! Optimice v0.13 brings bunch of bug fixes and stability. Also there is some initial documentation as a FAQ in trunk/docs that you should check. SVN will be updated more often than releases in Downloads so you should update code before usage :) Drop me an email if you find bugs or run into issues.

18-06-2011: .../o/ Optimice v0.12 is out. No new optimization algorithms but better code layout and more stable.

13-06-2011: \o Optimice v0.11 is deprecated as of now. Fixed many bugs in new version that will be out during the weekend.

01-03-2011: Yo! Optimice v0.11 is OUT. This should be more user friendly than previous release (and more stable, faster, better). No optimization were added to this release but this release uses NASM for assembling code. This solves many problems with native IDA assembler() so less execptions :), but this means you have to install NASM.
Send bug reports!

28-02-2011: Short movie in download section that shows how to use new optimice version that will be released in a few days. This will be a first usable (by a larger population) release of code. Many fixes, switched to NASM for assembling...

03-01-2011: New release in download section.

This plugin enables you to remove some common obfuscations and rewrite code to a new segment. Currently supported optimizations are:
  * Dead code removal
  * JMP merging
  * JCC opaque predicate removal
  * Pattern based deobfuscations

Plugin was tested with IDA 6 (versions 5.6+ should work, versions <5.6 should be supported when I switch to NASM for assembling optimized code).