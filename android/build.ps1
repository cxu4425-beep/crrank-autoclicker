# 不用 Gradle，直接用 Android SDK 工具建置 APK
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$bt = Get-ChildItem "$sdk\build-tools" | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName
$plat = Get-ChildItem "$sdk\platforms" | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName
$jar = "$plat\android.jar"
$out = "$here\out"
$apkName = "CRRank自動收成.apk"

function Run($exe, [string[]]$a) { & $exe @a; if ($LASTEXITCODE -ne 0) { throw "$exe 失敗 ($LASTEXITCODE)" } }

if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force "$out\gen", "$out\classes" | Out-Null

Write-Host "1/6 編譯資源"
Run "$bt\aapt2.exe" @("compile", "--dir", "$here\res", "-o", "$out\res.zip")
Run "$bt\aapt2.exe" @("link", "-o", "$out\base.apk", "-I", $jar, "--manifest", "$here\AndroidManifest.xml",
    "-A", "$here\assets", "--java", "$out\gen", "--min-sdk-version", "24", "--target-sdk-version", "34",
    "--version-code", "15", "--version-name", "2.3", "$out\res.zip")

Write-Host "2/6 編譯 Java"
$srcs = @(Get-ChildItem -Recurse "$here\src", "$out\gen" -Filter *.java | ForEach-Object FullName)
Run "javac" (@("-encoding", "UTF-8", "-source", "8", "-target", "8", "-Xlint:-options", "-bootclasspath", "$jar;$bt\core-lambda-stubs.jar", "-d", "$out\classes") + $srcs)

Write-Host "3/6 轉成 dex"
$classes = @(Get-ChildItem -Recurse "$out\classes" -Filter *.class | ForEach-Object FullName)
Run "$bt\d8.bat" (@("--release", "--min-api", "24", "--lib", $jar, "--output", $out) + $classes)

Write-Host "4/6 打包"
python -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1],'a'); z.write(sys.argv[2],'classes.dex'); z.close()" "$out\base.apk" "$out\classes.dex"
Run "$bt\zipalign.exe" @("-f", "-p", "4", "$out\base.apk", "$out\aligned.apk")

Write-Host "5/6 簽章"
$ks = "$here\crrank-release.jks"
if (-not (Test-Path $ks)) {
    Run "keytool" @("-genkeypair", "-keystore", $ks, "-alias", "crrank", "-keyalg", "RSA", "-keysize", "2048",
        "-validity", "10000", "-storepass", "crrank123", "-keypass", "crrank123", "-dname", "CN=CR Rank Auto Harvest")
}
Run "$bt\apksigner.bat" @("sign", "--ks", $ks, "--ks-pass", "pass:crrank123", "--key-pass", "pass:crrank123",
    "--out", "$here\$apkName", "$out\aligned.apk")

Write-Host "6/6 驗證"
Run "$bt\apksigner.bat" @("verify", "$here\$apkName")
Write-Host "完成：$here\$apkName"
