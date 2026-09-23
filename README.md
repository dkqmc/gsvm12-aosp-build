# gsvm12-aosp-build

在云端构建 **AOSP 12 (android-12.0.0_r34) arm64 系统镜像**，产物用于自建安卓二次虚拟化环境的 guest 镜像内容。本地不占磁盘，构建放在 CI 上跑。

## 已确认的事实（影响方案选择）

- 上游镜像源（清华 TUNA AOSP mirror）**不提供任何在线编译服务**，只镜像 git 仓库本身。其帮助页 FAQ 原文：「本仓库镜像的是 AOSP 的 git 仓库，不是系统镜像或者开发工具下载」。原文存档见 `tuna_aosp_help.txt`。
- 该镜像的 `aosp-monthly/aosp-latest.tar` 初始化包（约 100.6 GiB）对普通 HTTP 客户端的 GET 请求返回 403，因此只能走 `repo init` + `repo sync`。
- 清华 `platform/manifest` 上 android-12 系列最新标签为 `android-12.0.0_r34`。
- 站方限制并发，`repo sync` 建议 `-j4`，更高并发会 503。

## CI 的真实约束

### runner 实测结果（run 35854241893，job 用时 29 分 26 秒，报告在 `probe-out/`）

| 项 | 实测值 |
|---|---|
| OS / 内核 | Ubuntu 24.04.5 LTS，6.17.0-azure |
| CPU | 4 核 AMD EPYC 7763 |
| 内存 | 15 GiB + 3 GiB swap |
| 磁盘 | 单盘 150G，根分区 ext4 145G，**清理前可用 87G** |
| 清理预装后 | dotnet 5.8G + android SDK 11G + hostedtoolcache 5.0G + miniconda 980M + powershell 1.4G 删掉 → **可用 114G（121,582,460,928 字节）** |
| 清华 git 带宽 | `git clone --depth=1 platform/build` = **21 MiB / 10 分 08 秒 ≈ 35 KiB/s** |
| aosp-monthly 包 | HEAD 200，**GET 403**（与客户端网络无关，Azure 侧同样被拒） |
| 清单 | `ls-remote` 可见 `android-12.0.0_r1 … r34`（30 个 r3x 标签） |

**结论：免费 GitHub Actions 编 AOSP 12 不可行**，三条独立硬墙各自致命——磁盘（源码就要 ~100GB，`out/` 无处放）、带宽（100GB 源码按 35KiB/s 要 35 天）、单 job 360 分钟上限。附带 4 核冷编译本身也是十几小时量级。

## 已选路线：S5 官方预编译镜像

放弃自建编译，改用 Google 通过 Android SDK 分发的 **AOSP 12 arm64 系统镜像**（纯 AOSP，不带 Google 服务）：

```
sdkmanager --install "system-images;android-31;default;arm64-v8a"
```

实测落地（`D:\Android\SDK\system-images\android-31\default\arm64-v8a`，共 4.2 GB，几分钟下完）：

| 文件 | 大小 | 实测格式 |
|---|---:|---|
| `system.img` | 4,306,501,632 | **GPT 磁盘镜像**：`vbmeta`(1MiB, AVB0) + `super`(4104MiB 动态分区容器) |
| `vendor.img` | 99,614,720 | GPT：单分区 `vendor` @1MiB，**ext4**，4KiB 块、23249 块、incompat=IMAGES,FLEX_BG |
| `kernel-ranchu` | 20,044,221 | gzip |
| `ramdisk.img` | 4,282,682 | 内嵌 cpio-newc |
| `userdata.img` / `encryptionkey.img` | 1 MiB / 18 MiB | — |
| `build.prop` / `advancedFeatures.ini` / `VerifiedBootParams.textproto` | 文本 | `DynamicPartition = on` |

`build.prop` 实测身份字段：

```
ro.system.build.fingerprint = Android/sdk_phone64_arm64/emulator64_arm64:12/SE1A.220621.001/8752307:userdebug/test-keys
ro.build.version.release = 12    ro.build.version.sdk = 31
ro.build.type = userdebug        ro.build.tags = test-keys
ro.product.cpu.abi = arm64-v8a   构建日期 2022-06-22 (8752307)
```

**注意**：`system.img` 里的文件系统不是裸 ext4，而是包在 **GPT + 动态分区 super** 里；取文件树需要 `lpunpack`/`debugfs` 这类真工具（在 Linux 上几分钟的事）。自搓 LP 解析试过，头部结构与常见 liblp 布局不一致，已放弃。

## 目录内容

- `.github/workflows/probe-runner.yml` —— runner 资源与镜像带宽探测（手动触发，可复跑）
- `probe-out/runner-probe-report.txt` —— 上面那张实测表的原始输出
- `scripts/gpt_ls.py` —— 解析镜像的 GPT 分区表并判定分区内文件系统类型
- `scripts/scan_fs.py` / `scripts/dump_at.py` / `scripts/dump_super.py` —— 扫 ext4/erofs 超级块、dump 指定偏移字节
- `scripts/lp_ls.py` —— LP 元数据解析尝试（**未成功**，头部结构与 liblp 常见布局不符，仅作留档）
- `tuna_aosp_help.{html,txt}`、`tuna_aosp_monthly.{html,txt}` —— 上游镜像帮助页存档
- `AndroidProducts.12.txt` —— AOSP 12 `build/make/target/product/AndroidProducts.mk` 存档（可选产品目标；含 `mainline_system_arm64`、`generic_system_arm64` 这类只编 system 侧的目标）

镜像本体不在本仓库（4.2 GB，且可直接用 `sdkmanager` 重新获取），落在：
`D:\Android\SDK\system-images\android-31\default\arm64-v8a`
