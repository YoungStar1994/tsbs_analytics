## BenchmarkSQL TPC-C 测试作业指导书

### 1. 概述与准备
- **文档目标与读者**
  - 帮助 DBA、性能工程师、开发人员以可重复的流程完成 TPC-C 场景的性能评测，并形成可对比的报告。
  - 提供安装、参数、监控、调优与非兼容数据库改造的实操指南。
- **TPC-C 简介**
  - 模拟订单、支付、配送、库存查询等 OLTP 事务负载，具有高并发、短事务、热点数据行等特征。
  - 常见观测指标：吞吐（TPS/每分钟事务数）、延迟（平均/中位/p95/p99）、错误与中止率、资源使用率（CPU/内存/IO/网络）。
  - 事务组合默认比例：New-Order 45、Payment 43、Order-Status 4、Delivery 4、Stock-Level 4（总计 100）。
- **名词与约定**
  - `terminals`：并发终端数（并发客户端线程数）。
  - `warehouses`：仓库数（数据规模与热点分布的核心维度）。
  - `rampup`：预热时长（min）。
  - `runMins`：压测持续时长（min）。
  - 事务 mix 比例：各事务类型的权重，默认 45/43/4/4/4。

### 2. 安装与环境
- **获取与编译**
  - 依赖：JDK 8 及以上、Ant 或 Gradle、对应数据库的 JDBC 驱动。
  - 获取：使用上游仓库或厂商/社区维护分支，下载源码或发行包。
  - 构建：
    - 使用 Ant：在项目根目录执行 `ant`，产物位于 `dist/`。
    - 使用 Gradle：执行 `./gradlew clean shadowJar`，产物位于 `build/libs/`。
- **目录结构**
  - `run/`：启动脚本与示例属性文件（如 `props.pg`、`props.mysql`）。
  - `sql.common/`：公共 SQL 脚本（DDL/DML 片段）。
  - `sql.<db>/`：特定数据库方言脚本（如 `sql.postgres/`、`sql.mysql/`）。
  - `src/`：Java 源码与事务实现。
  - `dist/` 或 `build/`：构建产物目录。
  - `misc/`：辅助脚本（如 OS 资源采集 `os_collector_linux.py`）。
- **推荐机器配置（基准机与数据库机）**
  - 单机数据库（示例：中高配 x86 服务器）
    - 基准机：16–32 vCPU、32–64 GB 内存、千兆以上网卡、SSD 本地盘。
    - 数据库机：16–64 vCPU、64–256 GB 内存、NVMe/SSD、尽量独立数据盘与 WAL/Redo 盘。
  - 分布式数据库（示例：3–9 节点集群）
    - 基准机：建议独立 1–3 台，32–64 vCPU、64–128 GB 内存、25GbE 网络。
    - 数据库集群：遵循官方 sizing，计算与存储分层时确保网络≥10–25GbE，低时延。
  - 并发与仓数（初始建议，后续根据监控调优）
    - 单机数据库：
      - 8 vCPU：`terminals` 16–32；`warehouses` 50–100
      - 16 vCPU：`terminals` 64–128；`warehouses` 100–300
      - 32 vCPU：`terminals` 128–256；`warehouses` 300–600
      - 64 vCPU：`terminals` 256–512；`warehouses` 600–1200
    - 分布式数据库（按集群总 vCPU 粗略估算）：
      - `terminals` 约为总 vCPU 的 1.5–3 倍起步；分布在多台基准机。
      - `warehouses` ≥ `terminals`，建议为 2–3 倍以降低热点与锁争用。
- **系统与内核准备**
  - 时间同步：Chrony/NTP 对齐，记录时区与时间源。
  - 文件句柄/进程数：`ulimit -n`≥ 1e5，`ulimit -u` 合理放宽。
  - 内存与大页：关闭透明大页（THP），按需配置 HugePages（数据库侧）；避免 swap 压力。
  - I/O 与调度：SSD/NVMe，I/O 调度器与写回策略按数据库最佳实践设置。
  - 网络：固定速率/双工，关闭省电特性，核对 MTU，一致的 NIC 中断亲和。

### 3. BenchmarkSQL 的安装使用
- **数据准备与装载**
  - 创建数据库与账户，授予建表/索引/加载权限；为测试专用库与用户。
  - 建表与索引：
    ```bash
    ./runSQL.sh props.<db> sql.<db>/tableCreates.sql
    ./runSQL.sh props.<db> sql.<db>/indexCreates.sql
    ```
  - 加载数据：
    ```bash
    ./runLoader.sh props.<db>
    ```
  - 约束/外键（如有单独脚本）：
    ```bash
    ./runSQL.sh props.<db> sql.<db>/foreignKeys.sql
    ```
- **典型运行方式**
  - 单客户端：
    ```bash
    ./runBenchmark.sh props.<db>
    ```
  - 多客户端/多基准机：为每台分配一份属性文件（分配不同 `terminals` 与结果目录），并行启动。
  - 输出目录：由 `resultDirectory` 指定，包含明细日志、聚合结果与（可选）OS 指标。
- **单机与分布式数据库的并发与仓数建议**
  - 单机数据库：以 CPU 饱和不抖动为目标，`terminals` 先取 2–4×vCPU；`warehouses` 随内存与磁盘能力增加，至少与 `terminals` 等量。
  - 分布式数据库：考虑分片/副本拓扑，确保仓库在逻辑与物理分片间均衡分布；总体并发逐步升压观测锁/热点与网络利用率。
- **运行前检查清单**
  - 连通性：JDBC 驱动、URL、端口、防火墙、TLS。
  - 账户权限：建表/索引/序列/事务所需权限齐备。
  - 磁盘/目录：结果输出、数据库数据盘空间与 IOPS 余量。
  - 配置快照：保存属性文件、数据库参数与版本信息。
  - 预热策略：设置 `rampup`，确保缓存与执行路径稳定。

### 4. 兼容与非兼容数据库的测试方法
- **兼容数据库测试步骤（开箱可用）**
  - 放置 JDBC 驱动到 `lib/`（或在 `run` 脚本中指明 classpath）。
  - 准备属性文件（示例字段）：
    ```properties
    db=postgres
    driver=org.postgresql.Driver
    conn=jdbc:postgresql://<host>:<port>/<db>
    user=tpcc
    password=tpcc
    warehouses=300
    loadWorkers=16
    terminals=128
    rampup=10
    runMins=30
    newOrderWeight=45
    paymentWeight=43
    orderStatusWeight=4
    deliveryWeight=4
    stockLevelWeight=4
    resultDirectory=results_%tY-%tm-%td_%tH%tM%tS
    osCollectorScript=./misc/os_collector_linux.py
    osCollectorInterval=1
    osCollectorDevices=net_<ifname> blk_<disk>
    ```
  - 运行建表、装载与压测步骤（见第 3 章）。
- **非兼容数据库改造指引**
  - 差异定位：数据类型（NUMERIC/DECIMAL/DATE/BOOLEAN）、自增机制（序列/IDENTITY）、函数/表达式、语法方言、事务隔离语义。
  - 文件改造清单：
    - `sql.common/*.sql` 与 `sql.<db>/*`：调整 DDL/DML、索引与约束；必要时引入触发器/函数替代。
    - `run/props.*` 与自定义 `*.properties`：填入驱动类名、连接串、用户口令与方言特定参数。
    - `storedprocedures/*` 或相关 Java 事务实现（如有方言耦合）：按目标数据库能力改写。
  - JDBC 与隔离级别：确认 `READ COMMITTED`/`REPEATABLE READ`/`SNAPSHOT` 等的等价性；必要时在连接串或会话级设置。
  - 验证方法：
    - 装载校验：记录装载行数、索引与约束状态。
    - 事务通过率：关注死锁/序列化失败重试后成功率。
    - 结果一致性：对比不同并发下的吞吐与延迟曲线是否合理。

### 5. 参数优化（BenchmarkSQL 侧）
- **负载模型参数**
  - `warehouses`：决定数据规模与热点分布，增大可降低争用但增加 IO。
  - `terminals`：并发度，逐步升压寻找拐点，避免 CPU 抖动与锁风暴。
  - `rampup`/`runMins`：预热与压测时长；两者与 `runTxnsPerTerminal` 按需二选一。
  - 事务权重：`newOrderWeight`、`paymentWeight`、`orderStatusWeight`、`deliveryWeight`、`stockLevelWeight`，总和 100。
- **装载参数**
  - `loadWorkers`：装载并发度，结合数据库批量写入能力与磁盘带宽调节。
  - 批量提交与索引：先装载后建索引/约束通常更快；或使用支持的批量插入模式。
- **客户端 JVM 优化**
  - 堆大小：`-Xms` 与 `-Xmx` 固定为 1–4 GB 视并发与日志量而定。
  - GC 策略：G1/Parallel GC 皆可，确保 `-Xlog:gc*` 或 `-XX:+PrintGCDetails` 记录以便复盘。
  - 线程/文件句柄：确认基准机极限高于 `terminals` 需要。
- **Think/Keying Time**
  - 若以最大吞吐为目标，可在配置或源码开关中关闭思考时间与键入时间；如需贴近规范仿真，应保持开启并记录参数。
- **错误处理与重试**
  - 死锁与可重试冲突：采用指数退避，限制最大重试次数，统计重试比率。
  - 超时与中止：明确统计口径，将异常纳入报告说明。
- **稳定性与预热**
  - 预热至少 5–15 分钟或直至 TPS/延迟收敛；舍弃预热期数据。
  - 结果取样窗口：压测期中段 60–80% 区间的稳态数据更具比较意义。

### 6. 资源监控与观测（基准机与数据库侧）
- **基准机监控**
  - OS 采集：`sar`、`pidstat`、`iostat -x 1`、`vmstat 1`、`dstat -tcmnd`、`jstat`（JVM）。
  - 集成采集：在属性中启用 `osCollectorScript`、`osCollectorInterval`、`osCollectorDevices`，随压测自动采集并归档。
  - 时间同步与留存：采样周期建议 1s；基于测试批次归档，保留原始文件。
- **数据库侧监控**
  - OS 层：CPU 利用率、上下文切换、磁盘利用率与等待、网络带宽与 RTT。
  - 数据库内部：活跃连接、锁/等待、缓冲/缓存命中、检查点/刷盘、SQL 慢日志分位、GC 或清理任务。
  - Prometheus/Grafana：部署 Node/DB Exporter，准备标准看板（TPS、延迟、锁、缓存、IO、网络）。
- **瓶颈定位路径**
  - CPU 饱和→SQL/锁争用→IO 等待→网络饱和→JVM/GC 停顿→配置不当（如日志同步）。

### 7. 配置文件与参数说明
- **`benchmarksql.properties` 字段分组说明**
  - 连接配置：`db`、`driver`、`conn`、`user`、`password`（必要时 `ssl` 等）。
  - 负载配置：`warehouses`、`terminals`、`rampup`、`runMins`/`runTxnsPerTerminal`、事务权重、`limitTxnsPerMin`（限速）。
  - 装载配置：`loadWorkers`（装载并发），是否分阶段建索引/外键。
  - 结果与日志：`resultDirectory`、日志级别、是否启用 OS 采集脚本与采样周期。
- **`run/` 目录脚本与变量**
  - `runSQL.sh`、`runLoader.sh`、`runBenchmark.sh`：分别执行 DDL/DML、装载与压测。
  - 参数覆盖顺序：脚本内默认值 < 属性文件值；同名字段取后者；为不同客户端准备独立属性文件。
- **`sql.common/` 与 `sql.<db>/`**
  - 公共脚本与方言脚本分离，优先使用 `sql.<db>/`；根据实际数据库方言进行替换或扩展。
- **结果输出与报告**
  - `resultDirectory` 支持时间占位符（如 `%tY-%tm-%td_%tH%tM%tS`）。
  - 关键文件：汇总统计、每事务类型统计、错误日志、（可选）OS 监控原始数据与图表。

### 8. 测试流程与交付物
- **端到端流程**
  1) 目标确认与范围界定 → 2) 环境与参数快照 → 3) 装载与校验 → 4) 预热 → 5) 升压寻优 → 6) 稳态采样 → 7) 复核与复现 → 8) 出具报告。
- **报告模板（建议包含）**
  - 环境：硬件/OS/内核/数据库版本、重要配置、拓扑与网络。
  - 基准参数：`warehouses`、`terminals`、`rampup`、`runMins`、权重、是否启用 think/keying。
  - 结果：整体 TPS、各事务 TPS、延迟分位、错误/中止与重试率。
  - 资源：CPU/内存/IO/网络曲线、数据库内部关键指标、瓶颈诊断。
  - 结论：最优点、退化点、配置建议与风险清单。
- **复现实验**
  - 固定版本与依赖、保存属性文件与脚本、记录随机种子与时间戳、保留监控原始数据。

### 9. 附录
- **并发与仓数选型参考（起步值，需按监控调优）**
  - 单机：8 vCPU→(16–32, 50–100)、16 vCPU→(64–128, 100–300)、32 vCPU→(128–256, 300–600)、64 vCPU→(256–512, 600–1200)。
  - 分布式：`terminals`≈1.5–3×总 vCPU；`warehouses`≥`terminals`，推荐 2–3×；多基准机并行。
- **常见问题与故障排查**
  - 连接失败：驱动缺失/版本不匹配、URL/端口/TLS、凭据或权限不足。
  - 语法不兼容：在 `sql.<db>/` 覆盖 DDL/DML，检查自增/序列/函数差异。
  - 装载缓慢：提高 `loadWorkers`、先装载后建索引/外键、确认磁盘与 WAL/Redo 带宽。
  - 吞吐抖动：CPU 抢占/频率波动、锁争用热点、GC 暂停、网络拥塞、检查点/刷盘抖动。
  - 高中止率：热行冲突、长事务/慢 SQL、隔离级别与重试策略不匹配。
- **参考资料**
  - BenchmarkSQL 上游仓库与社区分支（获取源码与脚本）。
  - TPC-C 规范要点与事务比例说明。
  - 数据库厂商性能调优与最佳实践文档。

