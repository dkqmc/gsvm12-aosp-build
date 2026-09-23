# gsvm12-aosp-build

在云端构建 **AOSP 12 (android-12.0.0_r34) arm64 系统镜像**，产物用于自建安卓二次虚拟化环境的 guest 镜像内容。本地不占磁盘，构建放在 CI 上跑。

## 已确认的事实（影响方案选择）

- 上游镜像源（清华 TUNA AOSP mirror）**不提供任何在线编译服务**，只镜像 git 仓库本身。其帮助页 FAQ 原文：「本仓库镜像的是 AOSP 的 git 仓库，不是系统镜像或者开发工具下载」。原文存档见 `tuna_aosp_help.txt`。
- 该镜像的 `aosp-monthly/aosp-latest.tar` 初始化包（约 100.6 GiB）对普通 HTTP 客户端的 GET 请求返回 403，因此只能走 `repo init` + `repo sync`。
- 清华 `platform/manifest` 上 android-12 系列最新标签为 `android-12.0.0_r34`。
- 站方限制并发，`repo sync` 建议 `-j4`，更高并发会 503。

## CI 的真实约束

| 约束 | 数值 | 对 AOSP 的影响 |
|---|---|---|
| 单 job 最长运行 | 360 分钟 | 冷编译大概率超时 |
| Actions cache 单仓总量 | 10 GB | 装不下 `out/`（150–300 GB 量级） |
| runner 硬件 | 待实测（见 probe 报告） | 核数直接决定编译时长 |

因此第一步不是编译，而是**测量**：`.github/workflows/probe-runner.yml` 会量出核数/内存/cgroup 限制、清理预装工具链后的根分区可用字节、从 CI 侧访问上游镜像的实际带宽、以及 `repo init` 后的清单规模（project 数、group 分布）。

## 候选构建路线（等探测数据定夺）

| 方案 | 说明 | 主要障碍 |
|---|---|---|
| S1 单 job 硬扛 | sync + `make systemimage` 塞进一个 job | 6h 上限 |
| S2 跨 job 续命 | 源码/产物分片存到 Release assets，每轮恢复 | cache 装不下，分片上传下载极慢且脆 |
| S3 ccache 分桶 | 靠 ccache 增量 | 首轮 ccache 也是空的 |
| S4 self-hosted runner | 云上一台 32–64 核 / 500GB 按量机器注册成 runner | 要花钱 |
| S5 上游预编译镜像 | 直接取 Google 官方 AOSP 12 arm64 镜像抽文件树 | 不算自建 |
| S6 折中 | 系统树来自 S5，CI 只编需要改的模块 | 只能算部分自建 |

## 目录内容

- `.github/workflows/probe-runner.yml` —— runner 资源与镜像带宽探测（手动触发）
- `tuna_aosp_help.{html,txt}`、`tuna_aosp_monthly.{html,txt}` —— 上游镜像帮助页存档
- `AndroidProducts.12.txt` —— AOSP 12 `build/make/target/product/AndroidProducts.mk` 存档（可选产品目标；含 `mainline_system_arm64`、`generic_system_arm64` 这类只编 system 侧的目标，能把 `out/` 压小）
