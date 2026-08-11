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
function Replace-StringsRecursively($node, $map) {
  if ($node -is [string]) {
    $s = $node
    foreach ($kv in $map.GetEnumerator()) {
      # Dùng string .Replace thay vì regex -replace để tránh regex injection.
      $s = $s.Replace($kv.Key, $kv.Value)
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
