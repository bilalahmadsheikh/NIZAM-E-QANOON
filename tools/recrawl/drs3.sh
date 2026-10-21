#!/bin/bash
grep -oE '(pdfUrlRaw|pdfUrl|fileUrl|downloadUrl|filePath|FilePath|FileUrl)[^;]{0,200}' /tmp/drs-d.html | head -8
grep -oE 'data-[a-z-]*(pdf|file|url)[a-z-]*="[^"]*"' /tmp/drs-d.html | head -8
grep -oE '/[A-Za-z]+/[A-Za-z]*(File|Pdf|Download|Stream)[A-Za-z]*[^"'"'"' ]{0,80}' /tmp/drs-d.html | sort -u | head -8
