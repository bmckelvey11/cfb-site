param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [string]$Pattern = '(?<minutes>\d+)m(?<seconds>\d+)s',

    [string]$DatePattern = '(?<date>\d{4}-\d{2}-\d{2})',

    [string]$DateFormat = 'yyyyMMdd',

    [int]$StartSequence = 1,

    [switch]$SceneTitle,

    [string]$OpenAIModel = 'gpt-5.4-mini',

    [switch]$Recurse,

    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

function Get-SafeNamePart {
    param([string]$Value)

    $invalidPattern = "[{0}]" -f ([regex]::Escape((-join [IO.Path]::GetInvalidFileNameChars())))
    return ([regex]::Replace($Value.Trim(), $invalidPattern, '_') -replace '\s+', '_')
}

function Get-MediaDuration {
    param([string]$FilePath)

    $ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
    if (-not $ffprobe) {
        throw "Pattern did not provide minutes/seconds and ffprobe was not found."
    }

    $durationText = & $ffprobe.Source -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 -- $FilePath
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($durationText)) {
        throw "Could not read media duration for '$FilePath'."
    }

    $totalSeconds = [int][math]::Round([double]::Parse($durationText, [Globalization.CultureInfo]::InvariantCulture))
    return @{
        Minutes = [int][math]::Floor($totalSeconds / 60)
        Seconds = [int]($totalSeconds % 60)
        TotalSeconds = $totalSeconds
    }
}

function Get-VideoOrientation {
    param([string]$FilePath)

    $ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
    if (-not $ffprobe) {
        throw "ffprobe was not found, so video orientation could not be read."
    }

    $dimensionsText = & $ffprobe.Source -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 -- $FilePath
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($dimensionsText)) {
        throw "Could not read video dimensions for '$FilePath'."
    }

    $parts = $dimensionsText.Trim().Split('x')
    if ($parts.Count -lt 2) {
        throw "Unexpected video dimensions for '$FilePath': $dimensionsText"
    }

    $width = [int]$parts[0]
    $height = [int]$parts[1]

    if ($height -gt $width) {
        return 'v'
    }

    return 'h'
}

function Get-DatePart {
    param(
        [IO.FileInfo]$File,
        [regex]$Regex,
        [string]$Format
    )

    $match = $Regex.Match($File.BaseName)
    if ($match.Success -and $match.Groups['date'].Success) {
        return ([datetime]::ParseExact($match.Groups['date'].Value, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)).ToString($Format)
    }

    return $File.CreationTime.ToString($Format)
}

function Get-SceneTitle {
    param(
        [string]$FilePath,
        [int]$TotalSeconds,
        [string]$Model
    )

    if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        throw "OPENAI_API_KEY is not set."
    }

    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpeg) {
        throw "ffmpeg was not found, so scene frames could not be extracted."
    }

    $tempDir = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $tempDir | Out-Null

    try {
        $positions = @(
            [math]::Max(0, [math]::Floor($TotalSeconds * 0.25)),
            [math]::Max(0, [math]::Floor($TotalSeconds * 0.50)),
            [math]::Max(0, [math]::Floor($TotalSeconds * 0.75))
        ) | Select-Object -Unique

        $content = @(
            @{
                type = 'input_text'
                text = @'
Create a short filename-safe scene label.
Format: visible body attributes of the main subject, then action.
Return only lowercase words joined by underscores.
Use 3 to 8 words total.
Do not include names, dates, punctuation, quotes, or extra explanation.
Use neutral physical descriptors such as hair color, body type, clothing state, pose, and setting.
Avoid graphic sexual wording and explicit anatomy.
'@
            }
        )

        $index = 0
        foreach ($position in $positions) {
            $framePath = Join-Path $tempDir ("frame_{0}.jpg" -f $index)
            & $ffmpeg.Source -hide_banner -loglevel error -ss $position -i $FilePath -frames:v 1 -vf 'scale=768:-2' -q:v 3 $framePath -y
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $framePath)) {
                throw "Could not extract scene frame at ${position}s."
            }

            $base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($framePath))
            $content += @{
                type = 'input_image'
                image_url = "data:image/jpeg;base64,$base64"
                detail = 'low'
            }
            $index++
        }

        $body = @{
            model = $Model
            input = @(
                @{
                    role = 'user'
                    content = $content
                }
            )
            max_output_tokens = 40
        } | ConvertTo-Json -Depth 10

        $response = Invoke-RestMethod `
            -Uri 'https://api.openai.com/v1/responses' `
            -Method Post `
            -Headers @{
                Authorization = "Bearer $env:OPENAI_API_KEY"
                'Content-Type' = 'application/json'
            } `
            -Body $body

        $rawTitle = $response.output_text
        if ([string]::IsNullOrWhiteSpace($rawTitle)) {
            $textParts = @()
            foreach ($item in $response.output) {
                foreach ($part in $item.content) {
                    if ($part.text) {
                        $textParts += $part.text
                    }
                }
            }
            $rawTitle = ($textParts -join ' ')
        }

        $slug = ($rawTitle.ToLowerInvariant() -replace '[^a-z0-9]+', '_' -replace '^_+|_+$', '')
        $words = @($slug -split '_' | Where-Object { $_ })
        $slug = ($words | Select-Object -First 8) -join '_'

        if ([string]::IsNullOrWhiteSpace($slug)) {
            return 'untitled_scene'
        }

        return $slug
    }
    finally {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$resolvedPath = (Resolve-Path -LiteralPath $Path).Path
$target = Get-Item -LiteralPath $resolvedPath

if ($target.PSIsContainer) {
    $searchOption = if ($Recurse) { [IO.SearchOption]::AllDirectories } else { [IO.SearchOption]::TopDirectoryOnly }
    $files = [IO.Directory]::EnumerateFiles($target.FullName, '*', $searchOption) |
        ForEach-Object { Get-Item -LiteralPath $_ }
} else {
    $files = @($target)
}

$regex = [regex]::new($Pattern, [Text.RegularExpressions.RegexOptions]::IgnoreCase)
$dateRegex = [regex]::new($DatePattern, [Text.RegularExpressions.RegexOptions]::IgnoreCase)
$sequenceByFolder = @{}

foreach ($file in $files | Sort-Object DirectoryName, Name) {
    $match = $regex.Match($file.BaseName)

    if ($match.Success -and $match.Groups['minutes'].Success -and $match.Groups['seconds'].Success) {
        $minutes = [int]$match.Groups['minutes'].Value
        $seconds = [int]$match.Groups['seconds'].Value
        $totalSeconds = ($minutes * 60) + $seconds
    } else {
        $duration = Get-MediaDuration $file.FullName
        $minutes = $duration.Minutes
        $seconds = $duration.Seconds
        $totalSeconds = $duration.TotalSeconds
    }

    $parent = $file.Directory
    $grandparent = if ($parent -and $parent.Parent) { $parent.Parent.Name } else { $parent.Name }
    $folderKey = $parent.FullName.ToLowerInvariant()

    if (-not $sequenceByFolder.ContainsKey($folderKey)) {
        $sequenceByFolder[$folderKey] = $StartSequence
    }

    $created = Get-DatePart -File $file -Regex $dateRegex -Format $DateFormat
    $orientation = Get-VideoOrientation $file.FullName
    $titlePart = if ($SceneTitle) { "_$(Get-SceneTitle -FilePath $file.FullName -TotalSeconds $totalSeconds -Model $OpenAIModel)" } else { '' }
    $sequence = '{0:D3}' -f $sequenceByFolder[$folderKey]
    $sequenceByFolder[$folderKey]++

    $baseName = '{0}_{1}m{2}s_{3}{4}_{5}{6}' -f (
        (Get-SafeNamePart $grandparent),
        $minutes,
        ('{0:D2}' -f $seconds),
        $created,
        $titlePart,
        $sequence,
        $orientation
    )

    $newName = "$baseName$($file.Extension)"
    $destination = Join-Path $parent.FullName $newName

    while ((Test-Path -LiteralPath $destination) -and ($destination -ne $file.FullName)) {
        $sequence = '{0:D3}' -f $sequenceByFolder[$folderKey]
        $sequenceByFolder[$folderKey]++
        $newName = ('{0}_{1}m{2}s_{3}{4}_{5}{6}{7}' -f (
            (Get-SafeNamePart $grandparent),
            $minutes,
            ('{0:D2}' -f $seconds),
            $created,
            $titlePart,
            $sequence,
            $orientation,
            $file.Extension
        ))
        $destination = Join-Path $parent.FullName $newName
    }

    if ($Apply) {
        Rename-Item -LiteralPath $file.FullName -NewName $newName
        Write-Output "Renamed: $($file.FullName) -> $destination"
    } else {
        Write-Output "Dry run: $($file.FullName) -> $destination"
    }
}
