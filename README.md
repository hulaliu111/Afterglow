# Afterglow 工作区

Afterglow 的网站源码、产品演示与设计成果。

- `outputs/afterglow/`：完整静态网站，包含电影、剧集、后续季和电影系列目录。
- `outputs/afterglow-showreel/`：产品演示相关成果。
- `outputs/afterglow-continuations/`：续作与剧集季数切换的验证截图和记录。
- `outputs/` 中的其他图片：页面与封面效果的设计记录。

## 本地预览

在工作区根目录运行：

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory outputs/afterglow
```

然后打开 <http://127.0.0.1:8765/>。

网站的数据维护和部署说明见 `outputs/afterglow/README.md`。部署时将网站根目录设为 `outputs/afterglow`。

`work/` 中的临时文件、本机配置、凭据和 Git 编译产物不纳入版本管理。网站目录保留原有本地 Git 元数据；本仓库保存其实际文件，而非子模块引用。
