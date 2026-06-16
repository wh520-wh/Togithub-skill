# .gitignore 模板（按项目类型）

`scan.py` 不负责生成 .gitignore——agent 在 Step 6 根据项目类型手动从下面挑。

## Python

```gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Testing
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# IDEs
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Jupyter
.ipynb_checkpoints
*.ipynb

# mypy / ruff
.mypy_cache/
.ruff_cache/
```

## Node.js

```gitignore
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# Build outputs
dist/
build/
.next/
.nuxt/
.output/
.cache/

# Environments
.env
.env.local
.env.*.local

# Testing
coverage/
.nyc_output

# IDEs
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Optional npm cache
.npm
.eslintcache
```

## Go

```gitignore
# Binaries
*.exe
*.exe~
*.dll
*.dll~
*.so
*.so.*
*.dylib
*.test
*.out

# Go workspace
go.work
go.work.sum

# Environments
.env
.env.local

# IDEs
.idea/
.vscode/

# OS
.DS_Store
Thumbs.db
```

## Rust

```gitignore
/target/
/Cargo.lock

# Environments
.env
.env.local

# IDEs
.idea/
.vscode/

# OS
.DS_Store
Thumbs.db
```

## Java / Kotlin (Gradle / Maven)

```gitignore
# Build outputs
target/
build/
out/
*.class
*.jar
*.war
*.ear

# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar
!**/src/main/**/build/
!**/src/test/**/build/

# IntelliJ / Android Studio
.idea/
*.iml
*.iws
*.ipr
local.properties

# Environments
.env
.env.local

# OS
.DS_Store
Thumbs.db
```

## C# / .NET

```gitignore
bin/
obj/
out/
*.user
*.suo
*.userprefs
*.cachefile
*.swp

.vs/
.vscode/

# NuGet
packages/
*.nupkg

# Environments
.env
.env.local

# OS
.DS_Store
Thumbs.db
```

## 通用兜底

无法识别项目类型时，至少加这几行：

```gitignore
# Environments
.env
.env.*
!.env.example

# IDEs
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Build
build/
dist/
target/
```
