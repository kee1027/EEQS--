# 导入所需的库
import pandas as pd
import numpy as np
import pytz
from pathlib import Path
from io import StringIO
from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from data.models import Station, WeatherData

# ---------------------------------------------------------------------------
# 数据根目录配置
# ---------------------------------------------------------------------------
DATA_DIR = Path(r"D:\Data\CSI_Data\LoggerNet")

# ---------------------------------------------------------------------------
# 北斗宽表站点定义全集（自动兼容旧备份文件中的旧站与新文件中的新站）
# ---------------------------------------------------------------------------
STATION_DEFINITIONS = [
    # 共同拥有的常规站点
    ('KW',    'KW_Header',    'KW_Snow_density'),
    ('JG',    'JG_Header',    'JG_Snow_Depth'),
    ('KYE',   'KYE_Header',   'KYE_Snow_Depth'),
    ('AKSL',  'AKSL_Header',  'AKSL_Snow_Depth'),
    ('SDHZ',  'SDHZ_Header',  'SDHZ_Snow_density'),
    ('HXC',   'HXC_Header',   'HXC_TRB3_RH'),

    # 现版北斗新增站点
    ('HSZ',   'HSZ_Header',   'HSZ_Snow_density'),
    ('HL',    'HL_Header',    'HL_Snow_Depth'),

    # 旧版北斗留存站点
    ('KKSLS', 'KKSLS_Header', 'KKSLS_Snow_density'),
    ('KKSLM', 'KKSLM_Header', 'KKSLM_RainSnow_HalfHour'),
]

# ---------------------------------------------------------------------------
# 可可苏里单站（HalfHour文件）字段映射字典
# ---------------------------------------------------------------------------
# 1. 降雪站（KKSLS）列映射
KKSL_SNOW_HALFHOUR_MAPPING = {
    'Batt_volt_Avg': 'batt_volt',
    'PTemp_Avg': 'ptemp',
    'Snow_Depth_Avg': 'snow_depth',
    'Snow_Depth_USH': 'snow_depth_ush',
    'ice_content_slape': 'ice_content_slape',
    'water_content_slape': 'water_content_slape',
    'density_slape': 'density_slape',
    'SWE_slape': 'swe_slape',
    'ice_content_horizontal': 'ice_content_horizontal',
    'water_content_horizontal': 'water_content_horizontal',
    'density_horizontal': 'density_horizontal',
    'SWE_horizontal': 'swe_horizontal',
    'Flux_Min_200cm': 'flux_min_200cm',
    'Flux_Avg_200cm': 'flux_avg_200cm',
    'Flux_Max_200cm': 'flux_max_200cm',
    'Flux_Std_200cm': 'flux_std_200cm',
    'Flux_Cum_200cm': 'flux_cum_200cm',
    'Wind_Min_200cm': 'wind_min_200cm',
    'Wind_Avg_200cm': 'wind_avg_200cm',
    'Wind_Max_200cm': 'wind_max_200cm',
}

# 2. 气象站（KKSLM）列映射
KKSL_AWS_HALFHOUR_MAPPING = {
    'Batt_volt_Avg': 'batt_volt',
    'PTemp_Avg': 'ptemp',
    'WS': 'ws',
    'WD': 'wd',
    'WD_STD': 'wd_std',
    'AirT_C_Avg': 'ta',
    'RH_Avg': 'rh',
    'VP_kPa_Avg': 'pvapor',
    'BP_hPa_Avg': 'pressure',
    'SW_in_Avg': 'sw_in',
    'RainSnow': 'rainsnow',
    'RainSnow_HalfHour': 'rainsnow_halfhour',
    # 土壤标准层温湿度
    'VWC_soil_T_10cm': 'vwc_soil_10cm',
    'VWC_soil_T_60cm': 'vwc_soil_60cm',
    'VWC_soil_T_100cm': 'vwc_soil_100cm',
    'T_soil_T_10cm': 't_soil_10cm',
    'T_soil_T_60cm': 't_soil_60cm',
    'T_soil_T_100cm': 't_soil_100cm',
}


# ---------------------------------------------------------------------------
# 1. 解析北斗 TOA5 宽格式文件
# ---------------------------------------------------------------------------
def _parse_toa5_dynamically(file_path: Path) -> pd.DataFrame | None:
    """
    动态解析北斗接收多站宽表。
    容错机制：如果某站点列不在文件头中，跳过该站，确保兼容历史备份与现版文件。
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        raise CommandError(f"无法读取文件 {file_path}: {e}")

    header_start_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('"TOA5"'):
            header_start_index = i
            break
    if header_start_index == -1:
        raise CommandError(f"在文件中找不到 TOA5 文件头: {file_path}")

    header_lines = [l.strip() for l in lines[header_start_index:header_start_index + 4]]
    data_lines = lines[header_start_index + 4:]
    all_columns = [col.strip('"') for col in header_lines[1].split(',')]

    df_wide = pd.read_csv(
        StringIO("".join(data_lines)),
        header=None,
        names=all_columns,
        na_values=['"NAN"', 'NAN', '""'],
        quotechar='"',
        sep=','
    )

    model_field_names = {f.name for f in WeatherData._meta.get_fields()}
    processed_rows = []

    for _, row in df_wide.iterrows():
        timestamp = row['TIMESTAMP']
        for station_prefix, start_col_name, end_col_name in STATION_DEFINITIONS:
            # 容错：当前文件没有该站点的列定义则安全跳过
            if start_col_name not in all_columns or end_col_name not in all_columns:
                continue

            start_idx = all_columns.index(start_col_name)
            end_idx = all_columns.index(end_col_name) + 1

            station_data_slice = row[start_idx:end_idx]
            new_row = {'timestamp': timestamp, 'station_name': station_prefix}
            for col_name, value in station_data_slice.items():
                base_name = col_name.replace(station_prefix + '_', '', 1).lower()
                if base_name in model_field_names:
                    new_row[base_name] = value
            processed_rows.append(new_row)

    return pd.DataFrame(processed_rows) if processed_rows else None


# ---------------------------------------------------------------------------
# 2. 解析单站点TOA5文件
# ---------------------------------------------------------------------------
def _parse_single_station_toa5(file_path: Path, station_name: str, column_mapping: dict) -> pd.DataFrame | None:
    """
    解析标准的单站点半小时 TOA5 文件，转换为长格式 DataFrame。
    """
    if not file_path.exists():
        return None

    try:
        # 跳过 TOA5 的第 0、2、3 行描述行，第 1 行为真正的字段名
        df = pd.read_csv(
            file_path,
            skiprows=[0, 2, 3],
            header=0,
            na_values=['"NAN"', 'NAN', '""', ''],
            quotechar='"',
            encoding='utf-8'
        )
    except Exception as e:
        raise CommandError(f"读取文件失败 {file_path}: {e}")

    if df.empty or 'TIMESTAMP' not in df.columns:
        return None

    processed_df = pd.DataFrame()
    processed_df['timestamp'] = df['TIMESTAMP']
    processed_df['station_name'] = station_name

    model_field_names = {f.name for f in WeatherData._meta.get_fields()}

    for src_col, model_field in column_mapping.items():
        if src_col in df.columns and model_field in model_field_names:
            processed_df[model_field] = df[src_col]

    return processed_df


# ---------------------------------------------------------------------------
# 3. 文件智能发现与排序
# ---------------------------------------------------------------------------
def _discover_files() -> list[tuple[str, Path]]:
    """
    精确扫描半小时高频数据文件（自动过滤掉 Day 日报文件和控制台文件）。
    北斗文件按修改时间升序排序（保证主文件更新覆盖 backup）。
    """
    tasks = []

    # 1.扫描北斗接收文件，包括历史存留
    beidou_files = [
        f for f in DATA_DIR.glob("两河源北斗接收_Data_Receive.dat*")
        if f.is_file() and not f.name.endswith(".tmp")
    ]
    beidou_files.sort(key=lambda p: p.stat().st_mtime)
    for f in beidou_files:
        tasks.append(('beidou', f))

    # 2.扫描KKSLS
    kksl_snow = DATA_DIR / "可可苏里降雪_KKSL_Snow_HalfHour.dat"
    if kksl_snow.exists():
        tasks.append(('kksl_snow', kksl_snow))

    # 3.扫描KKSLM
    kksl_aws = DATA_DIR / "可可苏里气象_KKSL_AWS_HalfHour.dat"
    if kksl_aws.exists():
        tasks.append(('kksl_aws', kksl_aws))

    return tasks


# ---------------------------------------------------------------------------
# 4. 多文件合并 + 清洗
# ---------------------------------------------------------------------------
def _merge_and_clean(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    合并所有长表 DataFrame，时区本地化，全局去重，清洗数值。
    keep='last' 保证新读取的文件覆盖旧备份中的相同时间戳。
    """
    merged = pd.concat(dfs, ignore_index=True)

    # 时区转换（东八区 Asia/Shanghai）
    shanghai_tz = pytz.timezone('Asia/Shanghai')
    merged['timestamp'] = pd.to_datetime(merged['timestamp']).dt.tz_localize(shanghai_tz)

    # 全局去重：同站点同时间戳只保留最后出现的记录
    merged.drop_duplicates(subset=['station_name', 'timestamp'], keep='last', inplace=True)

    # 数值清洗
    data_cols = [f.name for f in WeatherData._meta.get_fields() if f.name not in ('id', 'station', 'timestamp')]
    for col in data_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors='coerce')

    merged.replace([np.inf, -np.inf], np.nan, inplace=True)
    return merged


# ---------------------------------------------------------------------------
# 5. 增量导入数据库
# ---------------------------------------------------------------------------
def _import_new_records(df: pd.DataFrame, stdout, style) -> dict:
    """
    只插入数据库中不存在的记录（增量写入）。
    """
    station_names = df['station_name'].unique()
    # 自动获取或创建 Station 记录（空库自动补齐站点）
    stations = {name: Station.objects.get_or_create(name=name)[0] for name in station_names}

    min_ts = df['timestamp'].min()
    max_ts = df['timestamp'].max()

    # 1. 一次性获取当前时间范围内的已存在记录
    existing_records = set(
        (station_id, int(ts.timestamp()))
        for station_id, ts in WeatherData.objects.filter(
            timestamp__range=(min_ts, max_ts)
        ).values_list('station_id', 'timestamp')
    )

    weather_objects = []
    skip_existing = 0
    seen_in_batch = set()

    for _, row in df.iterrows():
        station_obj = stations[row['station_name']]
        py_timestamp = row['timestamp'].to_pydatetime()
        lookup_key = (station_obj.id, int(py_timestamp.timestamp()))

        if lookup_key in existing_records or lookup_key in seen_in_batch:
            skip_existing += 1
            continue

        seen_in_batch.add(lookup_key)

        data_defaults = row.to_dict()
        data_defaults.pop('timestamp', None)
        data_defaults.pop('station_name', None)
        defaults_cleaned = {k: v for k, v in data_defaults.items() if pd.notna(v)}

        weather_objects.append(
            WeatherData(
                station=station_obj,
                timestamp=py_timestamp,
                **defaults_cleaned
            )
        )

    # 2. 批量落库
    records_created = len(weather_objects)
    if weather_objects:
        stdout.write(f"  正在向数据库批量写入 {records_created} 条新记录...")
        WeatherData.objects.bulk_create(weather_objects, batch_size=2000, ignore_conflicts=True)
    else:
        stdout.write("  没有新的数据需要写入。")

    return {
        'records_created': records_created,
        'skip_existing': skip_existing,
        'total_unique': len(df),
    }


# ---------------------------------------------------------------------------
# Django BaseCommand 入口
# ---------------------------------------------------------------------------
class Command(BaseCommand):
    help = '增量解析北斗接收文件与可可苏里单站半小时数据文件并入库 PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            nargs='+',
            help='手动指定一个或多个数据文件路径。'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='解析和清洗数据，但不保存到数据库。'
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self._execute_import(*args, **options)
        else:
            with transaction.atomic():
                self._execute_import(*args, **options)

    def _execute_import(self, *args, **options):
        is_dry_run = options['dry_run']
        manual_files = options['file']

        # ---------------------------------------------------------------
        # 1. 发现文件
        # ---------------------------------------------------------------
        tasks = []
        if manual_files:
            self.stdout.write(self.style.WARNING("[Manual] 使用手动指定的文件:"))
            for f_str in manual_files:
                p = Path(f_str)
                if "Snow" in p.name:
                    ftype = 'kksl_snow'
                elif "AWS" in p.name:
                    ftype = 'kksl_aws'
                else:
                    ftype = 'beidou'
                tasks.append((ftype, p))
                self.stdout.write(f"  - [{ftype}] {p}")
        else:
            tasks = _discover_files()
            self.stdout.write("[Auto] 智能扫描半小时高频数据文件...")
            if not tasks:
                self.stdout.write(self.style.WARNING("  未找到任何有效数据文件。"))
                return
            for ftype, f in tasks:
                self.stdout.write(f"  - [{ftype}] {f.name}")

        # ---------------------------------------------------------------
        # 2. 解析文件
        # ---------------------------------------------------------------
        self.stdout.write("[Parse] 开始解析文件...")
        dfs = []
        for ftype, f in tasks:
            df = None
            if ftype == 'beidou':
                df = _parse_toa5_dynamically(f)
            elif ftype == 'kksl_snow':
                df = _parse_single_station_toa5(f, 'KKSLS', KKSL_SNOW_HALFHOUR_MAPPING)
            elif ftype == 'kksl_aws':
                df = _parse_single_station_toa5(f, 'KKSLM', KKSL_AWS_HALFHOUR_MAPPING)

            if df is not None and not df.empty:
                dfs.append(df)
                self.stdout.write(f"  {f.name}: 提取到 {len(df)} 行数据")
            else:
                self.stdout.write(self.style.WARNING(f"  {f.name}: 无有效记录或文件为空"))

        if not dfs:
            self.stdout.write(self.style.WARNING("[Parse] 所有文件均无有效数据，退出。"))
            return

        # ---------------------------------------------------------------
        # 3. 合并与清洗
        # ---------------------------------------------------------------
        self.stdout.write("[Merge] 合并所有来源数据并清洗去重...")
        df_all = _merge_and_clean(dfs)
        self.stdout.write(f"  清洗合并完成，全库唯一记录数: {len(df_all)} 条")

        if is_dry_run:
            self.stdout.write(self.style.WARNING("\n--- Dry-run 模式：仅测试解析，未向数据库写入 ---"))
            return

        # ---------------------------------------------------------------
        # 4. 入库
        # ---------------------------------------------------------------
        self.stdout.write("[DB] 执行增量批量入库...")
        stats = _import_new_records(df_all, self.stdout, self.style)

        self.stdout.write(self.style.SUCCESS(
            f"\n数据导入完成:\n"
            f"  处理文件数:     {len(tasks)}\n"
            f"  涉及站点数:     {df_all['station_name'].nunique()} 个站点\n"
            f"  解析唯一总记录: {stats['total_unique']}\n"
            f"  跳过已有记录:   {stats['skip_existing']}\n"
            f"  本次新增入库:   {stats['records_created']}\n"
        ))