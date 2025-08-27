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

- **预检清单（Pre-flight Checks）**
  - 环境与版本：
    ```bash
    uname -a
    cat /etc/os-release | sed -n '1,5p'
    java -version
    ant -version || ./gradlew -v
    ```
  - 时间同步：
    ```bash
    timedatectl | sed -n '1,8p'
    chronyc sources -v | sed -n '1,10p' || echo "chrony not installed"
    ```
  - 资源上限与内核参数：
    ```bash
    ulimit -n
    ulimit -u
    sysctl vm.swappiness
    cat /sys/kernel/mm/transparent_hugepage/enabled
    ```
  - 网络与磁盘健康：
    ```bash
    ping -c 3 <db_host>
    iperf3 -c <db_host> -t 10   # 需要 iperf3 服务端
    iostat -x 1 3 | sed -n '1,40p'
    ```

### 2. 安装与环境
- **获取与编译**
  - 依赖：JDK 8 及以上、Ant 或 Gradle、对应数据库的 JDBC 驱动。
  - 获取：使用上游仓库或厂商/社区维护分支，下载源码或发行包。
  - 构建：
    - 使用 Ant：在项目根目录执行 `ant`，产物位于 `dist/`。
    - 使用 Gradle：执行 `./gradlew clean shadowJar`，产物位于 `build/libs/`。
- **详细安装步骤（示例）**
  1) 安装依赖：
     ```bash
     # Debian/Ubuntu
     sudo apt update && sudo apt install -y openjdk-11-jdk ant git unzip
     # RHEL/CentOS/Rocky
     sudo yum install -y java-11-openjdk-devel ant git unzip
     ```
  2) 获取源码并构建：
     ```bash
     git clone <benchmarksql_repo_url>
     cd benchmarksql
     ant  # 或 ./gradlew clean shadowJar
     ls -l dist/ || ls -l build/libs/
     ```
  3) 放置 JDBC 驱动：
     ```bash
     mkdir -p lib
     cp /path/to/jdbc/*.jar lib/
     ```
  4) 验证 classpath 与脚本：
     ```bash
     grep -n "classpath" run/*.sh | sed -n '1,40p'
     ```
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

- **OS/内核调优（参考建议，按安全与合规评估采纳）**
  - 永久配置 `/etc/sysctl.d/99-benchmark.conf`（示例）：
    ```
    vm.swappiness=1
    vm.dirty_background_ratio=5
    vm.dirty_ratio=20
    fs.file-max=1048576
    net.core.somaxconn=1024
    net.core.netdev_max_backlog=250000
    net.ipv4.tcp_max_syn_backlog=4096
    net.ipv4.ip_local_port_range=10000 65535
    net.ipv4.tcp_fin_timeout=15
    net.ipv4.tcp_tw_reuse=1
    net.core.rmem_max=134217728
    net.core.wmem_max=134217728
    net.ipv4.tcp_rmem=4096 87380 134217728
    net.ipv4.tcp_wmem=4096 65536 134217728
    ```
    应用：`sudo sysctl --system`
  - 关闭 THP：
    ```bash
    echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
    echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
    ```
  - CPU 频率与调优：
    ```bash
    # 设置性能模式（不同发行版命令可能不同）
    sudo cpupower frequency-set -g performance || true
    sudo tuned-adm profile throughput-performance || true
    ```
  - NIC 与中断亲和：
    ```bash
    sudo ethtool -G <iface> rx 4096 tx 4096 || true
    cat /proc/interrupts | grep <iface>
    # 结合 RPS/XPS 设置 /sys/class/net/<iface>/queues/*/rps_cpus
    ```
- **快速自检脚本（可选）**
  ```bash
  #!/usr/bin/env bash
  set -e
  echo "== OS =="; uname -a; cat /etc/os-release | sed -n '1,5p'
  echo "== Time =="; timedatectl | sed -n '1,8p'
  echo "== Java/Ant =="; java -version; ant -version || true
  echo "== Limits =="; echo "nofile=$(ulimit -n)"; echo "nproc=$(ulimit -u)"
  echo "== THP =="; cat /sys/kernel/mm/transparent_hugepage/enabled
  echo "== Disks =="; iostat -x 1 2 | sed -n '1,40p'
  ```

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
- **属性文件示例（PostgreSQL）**
  ```properties
  db=postgres
  driver=org.postgresql.Driver
  conn=jdbc:postgresql://<host>:5432/tpcc
  user=tpcc
  password=tpcc
  warehouses=300
  loadWorkers=16
  terminals=128
  rampup=10
  runMins=30
  # 事务权重
  newOrderWeight=45
  paymentWeight=43
  orderStatusWeight=4
  deliveryWeight=4
  stockLevelWeight=4
  # 结果与监控
  resultDirectory=results_pg_%tY-%tm-%td_%tH%tM%tS
  osCollectorScript=./misc/os_collector_linux.py
  osCollectorInterval=1
  osCollectorDevices=net_ens3 blk_nvme0n1
  ```
- **属性文件示例（MySQL 兼容）**
  ```properties
  db=mysql
  driver=com.mysql.cj.jdbc.Driver
  conn=jdbc:mysql://<host>:3306/tpcc?useSSL=false&serverTimezone=UTC
  user=tpcc
  password=tpcc
  warehouses=300
  loadWorkers=16
  terminals=128
  rampup=10
  runMins=30
  resultDirectory=results_mysql_%tY-%tm-%td_%tH%tM%tS
  osCollectorScript=./misc/os_collector_linux.py
  osCollectorInterval=1
  osCollectorDevices=net_ens3 blk_nvme0n1
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

- **验证 SQL（装载后）**
  - 行数与键范围：
    ```sql
    -- PostgreSQL/MySQL 类似
    SELECT COUNT(*) FROM warehouse;
    SELECT COUNT(*) FROM district;
    SELECT COUNT(*) FROM customer;
    SELECT COUNT(*) FROM history;
    SELECT COUNT(*) FROM orders;
    SELECT COUNT(*) FROM order_line;
    SELECT COUNT(*) FROM stock;
    ```
  - 索引存在性：
    ```sql
    -- PostgreSQL 示例
    \d+ customer
    \d+ orders
    ```

- **多客户端编排（多基准机并行）**
  - 节点清单 `clients.txt`：
    ```
    bench01 /opt/bmsql/run/props.pg.01 64 results_pg_01
    bench02 /opt/bmsql/run/props.pg.02 64 results_pg_02
    bench03 /opt/bmsql/run/props.pg.03 64 results_pg_03
    ```
  - 远程启动脚本 `start_all.sh`：
    ```bash
    #!/usr/bin/env bash
    set -euo pipefail
    while read host props terms outdir; do
      ssh -o StrictHostKeyChecking=no $host "cd $(dirname $props)/.. && sed -i 's/^terminals=.*/terminals=$terms/' $props && nohup ./run/runBenchmark.sh $props > $outdir.log 2>&1 &"
    done < clients.txt
    ```
  - 结果汇总：将各 `resultDirectory` 下的聚合文件（如 `summary.csv`）集中统计，统一绘图。

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
  - 最小改造示例：
    - 自增列：将 PostgreSQL `SERIAL`/`BIGSERIAL` 替换为目标数据库的自增关键字或序列触发器。
    - 分页语法：`LIMIT ? OFFSET ?` 替换为 `FETCH NEXT ? ROWS` 或数据库自有语法。
    - 时间函数：`CURRENT_TIMESTAMP`、`now()` 等按方言替换。

- **数据库专项准备（示例）**
  - PostgreSQL（示例建议，按场景与版本调整）：
    ```sql
    -- 连接/会话
    SHOW max_connections;  -- 确保高于 terminals 总和（含余量）
    -- 主要参数（需重启/重载）
    ALTER SYSTEM SET shared_buffers='25%';
    ALTER SYSTEM SET wal_compression=on;
    ALTER SYSTEM SET checkpoint_timeout='30min';
    ALTER SYSTEM SET max_wal_size='64GB';
    ALTER SYSTEM SET effective_io_concurrency=256;
    ALTER SYSTEM SET synchronous_commit=off;  -- 最大吞吐场景
    SELECT pg_reload_conf();
    ```
  - MySQL/InnoDB（示例建议，按版本/发行版校准）：
    ```
    innodb_buffer_pool_size = 50G
    innodb_log_file_size = 4G
    innodb_flush_log_at_trx_commit = 2     # 最大吞吐场景
    innodb_flush_method = O_DIRECT
    sync_binlog = 0                        # 非生产测试
    max_connections = 4096
    ```

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

- **调参方法学（分阶段搜索策略）**
  1) 固定 `warehouses`（如 300），以 `terminals` 梯度 32→64→128→256 升压；记录系统资源与 TPS/延迟；定位膝点（knee）。
  2) 在膝点附近微调 `warehouses`（±50%），寻找更优的争用与 IO 平衡。
  3) 设定稳定 `rampup`（10–15 min）与较长 `runMins`（30–60 min）获取稳态统计。
  4) 若中止率高：
     - 提高 `warehouses` 与热点扩散；
     - 检查索引、锁与长事务；
     - 增加客户端重试退避。
  5) 对比不同 GC 策略与堆大小，避免频繁 Full GC 或 Stop-The-World 超过 p99 延迟阈值。

- **结果判读与拐点识别**
  - 将 TPS 随 `terminals` 绘图；拐点前近线性增长，拐点后 TPS 平台或下降且 p95/p99 急升。
  - CPU>85% 且 p95 急升多为 CPU 饱和或锁争用；IO util>80% 伴随 svctm/wait 升高多为 IO 瓶颈。
  - 网络收发逼近上限且 RTT 抖动，考虑多网卡/链路汇聚或多机位分流。
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

- **常用命令与示例**
  ```bash
  # CPU/进程
  mpstat -P ALL 1 | tee cpu.txt
  pidstat -t -p $(pgrep -f benchmarksql | tr '\n' ',') 1 | tee pid.txt
  # 磁盘
  iostat -x 1 | tee iostat.txt
  # 网络
  sar -n DEV 1 | tee net.txt
  # JVM GC（需启用日志）
  jstat -gcutil $(pgrep -f benchmarksql | head -n1) 1 300 | tee gc.txt
  ```

- **Prometheus 集成（简要）**
  - 基准机与数据库机安装 Node Exporter；数据库按厂商提供的 Exporter 安装。
  - Grafana 导入通用看板，关键图：整体 TPS、p50/p95/p99 延迟、CPU、LoadAvg、磁盘 util/%iowait、网络吞吐、锁等待。
  - 典型 PromQL：
    - `rate(node_cpu_seconds_total{mode="idle"}[1m])` 推算 CPU 使用率。
    - `rate(node_disk_read_bytes_total[1m])`、`rate(node_disk_written_bytes_total[1m])`。

- **数据库内部观测（示例）**
  - PostgreSQL：
    ```sql
    SELECT wait_event_type, wait_event, COUNT(*)
    FROM pg_stat_activity
    WHERE state='active'
    GROUP BY 1,2 ORDER BY 3 DESC;

    SELECT locktype, mode, COUNT(*) FROM pg_locks GROUP BY 1,2;

    SELECT * FROM pg_stat_bgwriter;  -- 检查 checkpoints/flush

    -- 若安装 pg_stat_statements
    SELECT calls,total_exec_time/1000 AS sec, mean_exec_time, rows
    FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;
    ```
  - MySQL/InnoDB：
    ```sql
    SHOW ENGINE INNODB STATUS\G
    SELECT * FROM performance_schema.events_statements_summary_by_digest
    ORDER BY SUM_TIMER_WAIT DESC LIMIT 10;
    SELECT * FROM information_schema.innodb_trx\G
    SELECT * FROM information_schema.innodb_locks\G
    ```
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

- **完整参数示例与释义（节选）**
  ```properties
  # 连接
  db=postgres                # 目标数据库类型（与 sql.<db>/ 对应）
  driver=org.postgresql.Driver
  conn=jdbc:postgresql://host:5432/tpcc
  user=tpcc
  password=tpcc
  # 装载
  warehouses=300             # 仓库数（数据规模）
  loadWorkers=16             # 装载并发线程
  # 运行
  terminals=128              # 并发终端数
  rampup=10                  # 预热分钟数
  runMins=30                 # 运行分钟数（或使用 runTxnsPerTerminal）
  # 权重（总和 100）
  newOrderWeight=45
  paymentWeight=43
  orderStatusWeight=4
  deliveryWeight=4
  stockLevelWeight=4
  # 限速（可选）
  limitTxnsPerMin=0          # 0 表示不限速
  # 日志与结果
  resultDirectory=results_%tY-%tm-%td_%tH%tM%tS
  osCollectorScript=./misc/os_collector_linux.py
  osCollectorInterval=1
  osCollectorDevices=net_ens3 blk_nvme0n1
  ```

- **高级/可选参数（不同分支可能差异，以所用版本为准）**
  - `terminalWarehouseFixed`：true 时每个终端固定绑定仓库，减少跨仓热点。
  - `terminalDistrictFixed`：true 时终端固定绑定某个 district，进一步减少冲突。
  - `useStoredProcedures`：若实现为存储过程可开启以减少往返（部分分支支持）。
  - `printScreen`/`log4j` 级别：控制控制台与文件日志冗长度，避免 IO 干扰。
  - `noshort`/`noCustomers` 等：部分分支用于禁用特定事务类型或路径。
  - `resultDirectory` 时间占位符：`%tY %tm %td %tH %tM %tS` 等组合。

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

- **SOP（标准作业步骤）**
  1) 预检：完成第 1–2 章检查并记录。
  2) 准备属性：复制 `run/props.<db>` 为 `props.test.<tag>`，填入连接、并发、仓数、结果目录。
  3) 建表与装载：执行建表、建索引、装载，验证行数与索引；记录时间与日志。
  4) 预热与试跑：`rampup=10`、`runMins=5`，验证无明显错误与中止风暴。
  5) 正式压测：逐级升压（示例：64→128→256 terminals），每级 `runMins≥30`；保存所有结果目录。
  6) 监控采集：开启 OS 采集与 Prometheus，看板截屏或导出 JSON。
  7) 稳态判定：选取每轮中段 60–80% 时间窗作为汇总样本。
  8) 交付产物：整理报告、属性文件、SQL 校验结果、监控原始数据与图表、版本清单。

- **验收标准（示例）**
  - 试跑阶段错误率 < 1%，正式阶段中止+重试成功率 ≥ 98%。
  - 稳态窗口内 p95 延迟抖动 < 10%，无 CPU/IO/网络持续饱和且无异常 spike。
  - 报告可复现：提供同构环境复跑指引与脚本，结果偏差在 ±5% 内。

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

- **校验 SQL 速查（节选）**
  ```sql
  -- 订单与行项目一致性（示例）
  SELECT o_id, COUNT(*) AS lines
  FROM order_line
  GROUP BY o_id
  ORDER BY lines DESC
  LIMIT 5;

  -- 库存热点分布
  SELECT s_w_id, COUNT(*) AS cnt
  FROM stock
  GROUP BY s_w_id
  ORDER BY cnt DESC;

  -- 最近支付记录
  SELECT * FROM history ORDER BY h_date DESC LIMIT 10;
  ```

- **TPCC 装载期期望基数（理论值）**
  - 设 `W = warehouses`：
    - `warehouse`：W
    - `district`：10 × W
    - `customer`：30,000 × W（每 district 3,000）
    - `history`：30,000 × W（对应每个 customer 一条初始付款）
    - `orders`：30,000 × W（每 district 3,000）
    - `new_order`：9,000 × W（每 district 最近 900 个订单为未交付）
    - `order_line`：≈ 315,000 × W（每订单 5–15 行，均值 10.5）
    - `item`：100,000（全局共享）
    - `stock`：100,000 × W（每仓每 item 一行）

- **基数校验 SQL（示例）**
  ```sql
  -- 以 W=300 示例：
  -- 期望：warehouse=300, district=3000, customer=9,000,000
  SELECT COUNT(*) FROM warehouse;         -- 应为 W
  SELECT COUNT(*) FROM district;          -- 应为 10*W
  SELECT COUNT(*) FROM customer;          -- 应为 30000*W
  SELECT COUNT(*) FROM history;           -- 应为 30000*W
  SELECT COUNT(*) FROM orders;            -- 应为 30000*W
  SELECT COUNT(*) FROM new_order;         -- 应为 9000*W
  SELECT COUNT(*) FROM order_line;        -- 约 315000*W（上下浮动）
  SELECT COUNT(*) FROM item;              -- 应为 100000
  SELECT COUNT(*) FROM stock;             -- 应为 100000*W
  ```

- **常见问题进阶排查**
  - TPS 波动但 CPU 未饱和：检查锁/等待、慢查询、检查点/刷盘、网络丢包/重传。
  - p99 偶发飙高：核对 GC 日志/Full GC、IO 等待长尾、后台维护任务（VACUUM/ANALYZE/备份）。
  - 中止率高：热点行（district/order 序列相关）、隔离级别冲突、row-level locking；可增加 `warehouses`/分片数。
  - 结果不可复现：确保属性、数据库参数、二进制版本一致；检查 NTP 偏移与基准机 CPU governor。

