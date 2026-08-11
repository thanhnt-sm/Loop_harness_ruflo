# Module tiện ích chung để tìm và thay thế chuỗi/placeholder trong cấu trúc JSON.
# Dùng chung cho package-template.ps1 và deploy-template.ps1 để tránh trùng lặp logic.

# Duyệt đệ quy cấu trúc JSON/PSObject và thu thập tất cả giá trị string.
function Find-Strings($node, [ref]$out) {
  if ($node -is [string]) {
    if ($out.Value -notcontains $node) { $out.Value += $node }
  } elseif ($node -is [array]) {
    foreach ($el in $node) { Find-Strings $el $out }
  } elseif ($node -is [PSCustomObject]) {
    foreach ($prop in $node.PSObject.Properties) { Find-Strings $prop.Value $out }
  }
}

# Thay thế các key trong $map bằng value tương ứng trên toàn bộ cấu trúc JSON.
# Sắp xếp key theo độ dài giảm dần để tránh thay thế một phần (partial replacement).
function Replace-StringsRecursively($node, $map) {
  if ($node -is [string]) {
    $s = $node
    $sortedKeys = $map.Keys | Sort-Object { $_.Length } -Descending
    foreach ($key in $sortedKeys) {
      # Dùng string .Replace thay vì regex -replace để tránh regex injection.
      $s = $s.Replace($key, $map[$key])
    }
    return $s
  } elseif ($node -is [array]) {
    return @($node | ForEach-Object { Replace-StringsRecursively $_ $map })
  } elseif ($node -is [PSCustomObject]) {
    $clone = [PSCustomObject]@{}
    foreach ($prop in $node.PSObject.Properties) {
      $clone | Add-Member -NotePropertyName $prop.Name -NotePropertyValue (Replace-StringsRecursively $prop.Value $map) -Force
    }
    return $clone
  }
  return $node
}

# Che giấu phần nhạy cảm trong đường dẫn trước khi in ra log.
# Thay thế USERPROFILE và APPDATA bằng alias [USER_HOME] / [APPDATA].
function Protect-LogPath($path) {
  if (-not $path -or $path -isnot [string]) { return $path }
  $s = $path
  if ($env:USERPROFILE -and $s.StartsWith($env:USERPROFILE, [System.StringComparison]::OrdinalIgnoreCase)) {
    $s = '[USER_HOME]' + $s.Substring($env:USERPROFILE.Length)
  } elseif ($env:APPDATA -and $s.StartsWith($env:APPDATA, [System.StringComparison]::OrdinalIgnoreCase)) {
    $s = '[APPDATA]' + $s.Substring($env:APPDATA.Length)
  }
  return $s
}

# Thay thế prefix đường dẫn aide-memory dạng ${USER_HOME}\...\nvm\vX.Y.Z\node_modules\aide-memory
# bằng placeholder {{AIDE_MEMORY_GLOBAL}}, tránh phụ thuộc vào version nvm hardcoded.
function Replace-AideMemoryPrefix($node) {
  $pattern = '\$\{USER_HOME\}\\AppData\\Roaming\\nvm\\v\d+\.\d+\.\d+\\node_modules\\aide-memory'
  if ($node -is [string]) {
    return [regex]::Replace($node, $pattern, '{{AIDE_MEMORY_GLOBAL}}')
  } elseif ($node -is [array]) {
    return @($node | ForEach-Object { Replace-AideMemoryPrefix $_ })
  } elseif ($node -is [PSCustomObject]) {
    $clone = [PSCustomObject]@{}
    foreach ($prop in $node.PSObject.Properties) {
      $clone | Add-Member -NotePropertyName $prop.Name -NotePropertyValue (Replace-AideMemoryPrefix $prop.Value) -Force
    }
    return $clone
  }
  return $node
}

# Chuẩn hóa các command chạy bash:
# - Chuyển backslash thành forward slash để Git Bash hiểu đúng đường dẫn.
# - Bọc đường dẫn trong dấu nháy kép nếu chứa dấu cách, tránh lỗi parse.
function Set-BashCommandSlashes($node) {
  if ($node -is [PSCustomObject]) {
    foreach ($prop in $node.PSObject.Properties) {
      if ($prop.Name -eq 'command' -and $prop.Value -is [string] -and $prop.Value -match '^\s*bash\s+') {
        $cmd = $prop.Value.Trim()
        if ($cmd -match '^bash\s+(.+)$') {
          $scriptPath = $matches[1].Trim()
          $scriptPath = $scriptPath.Replace('\', '/')
          if ($scriptPath -match '\s' -and -not ($scriptPath.StartsWith('"') -or $scriptPath.StartsWith("'"))) {
            $scriptPath = '"' + $scriptPath + '"'
          }
          $prop.Value = "bash $scriptPath"
        }
      } else {
        Set-BashCommandSlashes $prop.Value
      }
    }
  } elseif ($node -is [array]) {
    foreach ($el in $node) { Set-BashCommandSlashes $el }
  }
}
