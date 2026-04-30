# 打包指南 - 将项目打包成 EXE 文件

本指南说明如何使用 PyInstaller 将微信教育代理项目打包成独立的 EXE 文件，无需用户配置 Python 环境即可直接运行。

## 前置条件

1. **已安装 PyInstaller**（你已经安装了✓）
2. **已安装项目依赖**

```bash
pip install -r wechat_edu_agent/requirements.txt
```

3. **项目结构完整**（确保 `wechat_edu_agent/` 目录下所有文件都存在）

## 打包步骤

### 第 1 步：安装额外依赖（可选但推荐）

```bash
pip install pyinstaller
```

### 第 2 步：确保 .env 配置存在

**重要**：打包前，用户需要在项目根目录创建 `.env` 文件，配置 LLM API：

```ini
# 必填：LLM API
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-your_key_here
LLM_MODEL=deepseek-chat

# 可选：搜索 API
SEARCH_PROVIDER=manual
# DASHSCOPE_API_KEY=sk-xxx
# TAVILY_API_KEY=tvly-xxx

OUTPUT_DIR=outputs
LLM_TEMPERATURE=0.7
```

**注意**：`.env` 文件 **不会** 被打进 EXE，用户需要在与 EXE 同目录放置 `.env`。

### 第 3 步：执行打包命令

#### 方式 A：使用 spec 文件（推荐）✅

```bash
python -m PyInstaller wechat_edu_agent.spec
```

#### 方式 B：直接命令行打包

```bash
pyinstaller ^
  --name "微信教育代理" ^
  --onedir ^
  --windowed ^
  --icon=icon.ico ^
  --hidden-import=wechat_edu_agent ^
  --hidden-import=openai ^
  --hidden-import=pydantic ^
  --hidden-import=dotenv ^
  --hidden-import=dashscope ^
  --add-data "wechat_edu_agent:wechat_edu_agent" ^
  wechat_edu_agent/main.py
```

### 第 4 步：找到生成的 EXE

打包完成后，生成的文件位于：

```
./dist/微信教育代理/
├── 微信教育代理.exe    ← 主程序
├── wechat_edu_agent/   ← 项目代码
├── _internal/          ← 依赖库
└── ... (其他文件)
```

## 部署和发布

### 给用户提供以下文件：

1. **整个 `./dist/微信教育代理/` 目录**
2. **.env 模板文件**（放在与 EXE 同目录）

```
用户目录/
├── 微信教育代理.exe
├── .env               ← 用户需要编辑此文件并配置 LLM API
└── wechat_edu_agent/  ← 项目代码和依赖
```

### 用户使用步骤：

1. 解压文件夹
2. 编辑 `.env`，填入自己的 LLM API Key
3. **双击 `微信教育代理.exe`** ✅

## 打包选项说明

| 选项 | 说明 | 推荐值 |
|------|------|--------|
| `--onedir` | 生成目录（包含依赖）vs `--onefile`（单文件） | `--onedir`（启动快，便于调试） |
| `--windowed` | 隐藏控制台窗口，仅显示 GUI | 使用（GUI 应用） |
| `--console` | 显示控制台窗口 | 不使用（已用 `--windowed`） |
| `--icon` | 自定义 EXE 图标 | 可选，指定 `.ico` 文件 |
| `--add-data` | 添加非Python文件（如配置文件） | `"src:dst"` 格式 |
| `--hidden-import` | 显式包含动态导入的模块 | 已在 spec 中配置 |

## 常见问题

### Q1：打包后 EXE 很大（>200MB）

**原因**：包含了所有依赖库  
**解决**：正常现象，openai / dashscope / pydantic 等库体积较大  
**优化**：使用 `--onefile` 生成单文件（会更大但便于分发）

### Q2：运行 EXE 时报错 "ModuleNotFoundError"

**检查**：
- `--hidden-import` 是否包含了该模块（已在 spec 中配置）
- 是否遗漏了 `--add-data` 中的数据文件
- **重新运行打包命令**

### Q3：如何自定义 EXE 名称和图标？

```bash
# 修改 spec 文件中的 name 参数
name='微信教育代理',  # ← 改这里

# 添加图标（先准备 icon.ico）
# 在 EXE 定义中添加：
icon='icon.ico',
```

### Q4：发布时能否将 .env 打进 EXE？

**不推荐**，因为：
- API Key 不应暴露在可执行文件中
- 用户无法修改配置
- 安全隐患

**推荐做法**：让用户在与 EXE 同目录放置 `.env` 文件。

### Q5：如何测试打包后的 EXE？

```bash
# 打包完成后
cd dist\微信教育代理

# 1. 创建 .env 文件并配置
# 2. 双击运行 微信教育代理.exe
# 3. 检查 GUI 是否正常启动和运行
```

## 完整命令速查

```bash
# 最简单：使用 spec 文件
python -m PyInstaller wechat_edu_agent.spec

# 清理旧文件后重新打包
rmdir /s /q build dist
python -m PyInstaller wechat_edu_agent.spec

# 使用 -w（Windows 简写）
pyinstaller -w --onedir --name "微信教育代理" wechat_edu_agent/main.py
```

## 下一步

1. ✅ 运行 `python -m PyInstaller wechat_edu_agent.spec`
2. ✅ 在 `./dist/微信教育代理/` 中找到 EXE
3. ✅ 创建 `.env` 文件并配置 API Key
4. ✅ 双击运行测试
5. ✅ 打包 `dist/微信教育代理/` 目录进行分发
