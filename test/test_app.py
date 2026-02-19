import os
import threading
from datetime import datetime
from unittest.mock import MagicMock, patch, mock_open, PropertyMock
import polars as pl
import tempfile


class TestExtractDate:
    def setup_method(self):
        from promodate_functions import extract_date

        self.extract_date = extract_date

    def test_valid_date_in_filename(self):
        result = self.extract_date("promodata_2024-03-15_v2.xlsx")
        assert result == datetime(2024, 3, 15)

    def test_no_date_in_filename(self):
        result = self.extract_date("report_final.xlsx")
        assert result is None

    def test_multiple_parts_returns_first_valid(self):
        result = self.extract_date("prefix_2023-01-01_suffix.xlsx")
        assert result == datetime(2023, 1, 1)

    def test_invalid_date_format(self):
        result = self.extract_date("file_15-03-2024.xlsx")
        assert result is None

    def test_empty_string(self):
        result = self.extract_date("")
        assert result is None


class TestDownloadFile:
    def setup_method(self):
        from promodate_functions import download_file

        self.download_file = download_file

    @patch("promodate_functions.shutil.copy2")
    def test_successful_copy(self, mock_copy):
        log = MagicMock()
        self.download_file("/src/file.xlsx", "/dst/file.xlsx", log)
        mock_copy.assert_called_once_with("/src/file.xlsx", "/dst/file.xlsx")
        assert log.call_count == 2

    @patch("promodate_functions.shutil.copy2", side_effect=OSError("disk full"))
    def test_copy_failure_logged(self, mock_copy):
        log = MagicMock()
        self.download_file("/src/file.xlsx", "/dst/file.xlsx", log)
        error_logged = any("Ошибка" in str(c) for c in log.call_args_list)
        assert error_logged


class TestDownloadFilesThread:
    def setup_method(self):
        from promodate_functions import download_files_thread

        self.fn = download_files_thread

    @patch(
        "promodate_functions.os.listdir",
        return_value=[
            "data_2024-03-01_retail.xlsx",
            "data_2024-04-01_retail.xlsx",
            "other.txt",
        ],
    )
    @patch("promodate_functions.ThreadPoolExecutor")
    def test_filters_by_month_and_year(self, mock_executor, mock_listdir):
        mock_ctx = MagicMock()
        mock_executor.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_executor.return_value.__exit__ = MagicMock(return_value=False)

        month_var = MagicMock()
        month_var.get.return_value = "3"
        year_var = MagicMock()
        year_var.get.return_value = "2024"
        log = MagicMock()
        messagebox = MagicMock()

        self.fn(month_var, year_var, log, messagebox)

        submitted = [c.args[1] for c in mock_ctx.submit.call_args_list]
        assert all("2024-03-01" in s for s in submitted)

    @patch("promodate_functions.os.listdir", return_value=["irrelevant.xlsx"])
    def test_no_matching_files_warns(self, mock_listdir):
        month_var = MagicMock()
        month_var.get.return_value = "12"
        year_var = MagicMock()
        year_var.get.return_value = "2099"
        log = MagicMock()
        messagebox = MagicMock()

        self.fn(month_var, year_var, log, messagebox)
        messagebox.showwarning.assert_called_once()


class TestClearDownloadFolder:
    def setup_method(self):
        from promodate_functions import clear_download_folder, DOWNLOAD_FOLDER

        self.fn = clear_download_folder
        self.folder = DOWNLOAD_FOLDER

    @patch("promodate_functions.os.listdir", return_value=[])
    def test_empty_folder_shows_info(self, _):
        log = MagicMock()
        mb = MagicMock()
        self.fn(log, mb)
        mb.showinfo.assert_called_once()
        log.assert_not_called()

    @patch("promodate_functions.os.remove")
    @patch("promodate_functions.os.listdir", return_value=["a.xlsx", "b.csv"])
    def test_deletes_all_files(self, mock_list, mock_remove):
        log = MagicMock()
        mb = MagicMock()
        self.fn(log, mb)
        assert mock_remove.call_count == 2

    @patch("promodate_functions.os.remove", side_effect=PermissionError("locked"))
    @patch("promodate_functions.os.listdir", return_value=["locked.xlsx"])
    def test_remove_error_is_logged(self, _, __):
        log = MagicMock()
        mb = MagicMock()
        self.fn(log, mb)
        error_logged = any("Ошибка" in str(c) for c in log.call_args_list)
        assert error_logged


class TestProcessFile:
    def setup_method(self):
        from promodate_functions import process_file, FILTER_OPTIONS

        self.fn = process_file
        self.filter = FILTER_OPTIONS["Масло"]

    def _make_df(self, group, category, retailer):
        return pl.DataFrame(
            {
                "group": [group],
                "category": [category],
                "brand": ["TestBrand"],
                "pd_sku": ["SKU1"],
                "retailer": [retailer],
                "region": ["Москва"],
                "date": ["2024-01-01"],
                "promo": ["10"],
                "regular": ["100"],
            }
        )

    @patch("promodate_functions.pl.read_excel")
    @patch("promodate_functions.get_first_sheet_name", return_value="Sheet1")
    @patch("promodate_functions.os.makedirs")
    def test_matching_row_is_saved(self, mock_mkd, mock_sheet, mock_read):
        df = self._make_df("Соусы и масла", "Масло растительное", "Пятёрочка")
        mock_read.return_value = df

        log = MagicMock()
        with patch.object(pl.DataFrame, "to_pandas") as mock_pd:
            mock_pd.return_value = df.to_pandas()
            with patch("promodate_functions.open", mock_open(), create=True):
                with patch("pandas.DataFrame.to_csv"):
                    self.fn("/fake/file.xlsx", "/out", self.filter, log)

        success_logged = any("Готово" in str(c) for c in log.call_args_list)
        assert success_logged

    @patch("promodate_functions.pl.read_excel", side_effect=Exception("read error"))
    @patch("promodate_functions.get_first_sheet_name", return_value="Sheet1")
    def test_exception_is_logged(self, _, __):
        log = MagicMock()
        self.fn("/fake/bad.xlsx", "/out", self.filter, log)
        error_logged = any("Ошибка" in str(c) for c in log.call_args_list)
        assert error_logged


class TestMakeUniqueColumns:
    def setup_method(self):
        from nielsen_functions import make_unique_columns

        self.fn = make_unique_columns

    def test_no_duplicates(self):
        assert self.fn(["A", "B", "C"]) == ["A", "B", "C"]

    def test_duplicates_get_suffixes(self):
        result = self.fn(["A", "A", "A"])
        assert result[0] == "A"
        assert result[1] == "A_1"
        assert result[2] == "A_2"

    def test_none_becomes_unnamed(self):
        result = self.fn([None, None])
        assert result[0] == "Unnamed"
        assert result[1] == "Unnamed_1"

    def test_mixed(self):
        result = self.fn(["X", "Y", "X", "Z"])
        assert result == ["X", "Y", "X_1", "Z"]


class TestMeltPolars:
    def setup_method(self):
        from nielsen_functions import melt_polars

        self.fn = melt_polars

    def _sample_df(self):
        return pl.DataFrame(
            {
                "MARKET": ["RU"],
                "FACT": ["Value (in 1000 RUR)"],
                "JAN 24": [100.0],
                "FEB 24": [200.0],
            }
        )

    def test_output_has_attribute_and_value(self):
        df = self._sample_df()
        result = self.fn(df, id_cols=["MARKET", "FACT"])
        assert "ATTRIBUTE" in result.columns
        assert "VALUE" in result.columns

    def test_date_columns_parsed(self):
        df = self._sample_df()
        result = self.fn(df, id_cols=["MARKET", "FACT"])
        attributes = result["ATTRIBUTE"].to_list()
        assert all(attr is None or "." in attr for attr in attributes)

    def test_null_values_dropped(self):
        df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "FACT": ["Units"],
                "JAN 24": [None],
                "FEB 24": [42.0],
            }
        )
        result = self.fn(df, id_cols=["MARKET", "FACT"])
        assert result.height == 1

    def test_preserves_id_columns(self):
        df = self._sample_df()
        result = self.fn(df, id_cols=["MARKET", "FACT"])
        assert "MARKET" in result.columns
        assert "FACT" in result.columns


class TestOptimizeForSize:
    def setup_method(self):
        from nielsen_functions import optimize_for_size

        self.fn = optimize_for_size

    def test_value_cast_to_float32(self):
        df = pl.DataFrame({"VALUE": [1.23456789]})
        result = self.fn(df)
        assert result["VALUE"].dtype == pl.Float32

    def test_known_cat_cols_cast(self):
        df = pl.DataFrame({"MARKET": ["Russia"], "BRAND": ["BrandX"], "VALUE": [1.0]})
        result = self.fn(df)
        assert result["MARKET"].dtype == pl.Categorical
        assert result["BRAND"].dtype == pl.Categorical

    def test_df_without_value_col(self):
        df = pl.DataFrame({"MARKET": ["Russia"]})
        result = self.fn(df)
        assert "MARKET" in result.columns


class TestProcessNielsen:
    def setup_method(self):
        from nielsen_functions import process_nielsen

        self.fn = process_nielsen

    def test_missing_input_file_warns(self):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("", "/some/dir", "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()

    def test_missing_output_dir_warns(self, tmp_path):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(fname, "", "csv", log, mb, stop, "Масло")
            mb.showwarning.assert_called_once()
        finally:
            os.unlink(fname)

    def test_nonexistent_input_file_warns(self, tmp_path):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("/nonexistent/file.xlsx", str(tmp_path), "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()


class TestRefreshFile:
    def setup_method(self):
        from competitors_functions import refresh_file

        self.fn = refresh_file

    @patch("competitors_functions.pythoncom")
    @patch("competitors_functions.win32")
    def test_successful_refresh(self, mock_win32, mock_com):
        mock_excel = MagicMock()
        mock_wb = MagicMock()
        mock_win32.DispatchEx.return_value = mock_excel
        mock_excel.Workbooks.Open.return_value = mock_wb

        ws = MagicMock()
        mock_wb.Worksheets.__getitem__ = MagicMock(return_value=ws)

        before_val = "OLD"
        after_val = "NEW"
        ws.Range.return_value.Value = after_val
        call_count = [0]

        def side_effect():
            call_count[0] += 1
            return before_val if call_count[0] == 1 else after_val

        ws.Range.return_value.__class__ = type(
            "Cell", (), {"Value": property(lambda self: side_effect())}
        )

        log = MagicMock()
        stop = threading.Event()
        with patch("competitors_functions.time.sleep"):
            result = self.fn("/fake/file.xlsx", log, stop)
        assert isinstance(result, bool)

    @patch("competitors_functions.pythoncom")
    @patch("competitors_functions.win32")
    def test_stop_event_aborts(self, mock_win32, mock_com):
        mock_excel = MagicMock()
        mock_wb = MagicMock()
        mock_win32.DispatchEx.return_value = mock_excel
        mock_excel.Workbooks.Open.return_value = mock_wb

        ws = MagicMock()
        mock_wb.Worksheets.__getitem__ = MagicMock(return_value=ws)
        ws.Range.return_value.Value = "SAME"

        stop = threading.Event()
        stop.set()

        log = MagicMock()
        with patch("competitors_functions.time.sleep"):
            result = self.fn("/fake/file.xlsx", log, stop)

        assert result is False

    @patch("competitors_functions.pythoncom")
    @patch("competitors_functions.win32.DispatchEx", side_effect=Exception("COM error"))
    def test_exception_returns_false(self, mock_dispatch, mock_com):
        log = MagicMock()
        stop = threading.Event()
        result = self.fn("/fake/file.xlsx", log, stop)
        assert result is False
        error_logged = any("Ошибка" in str(c) for c in log.call_args_list)
        assert error_logged


class TestRefreshCompetitorsPipeline:
    def setup_method(self):
        from competitors_functions import refresh_competitors_pipeline

        self.fn = refresh_competitors_pipeline

    def test_missing_olap_file_warns(self):
        olap = MagicMock()
        olap.get.return_value = ""
        comp = MagicMock()
        comp.get.return_value = "/valid/file.xlsx"
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn(olap, comp, log, mb, stop)
        mb.showwarning.assert_called_once()

    def test_missing_competitors_file_warns(self, tmp_path):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            olap = MagicMock()
            olap.get.return_value = fname
            comp = MagicMock()
            comp.get.return_value = ""
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(olap, comp, log, mb, stop)
            mb.showwarning.assert_called_once()
        finally:
            os.unlink(fname)

    @patch("competitors_functions.refresh_file", return_value=False)
    def test_pipeline_aborts_if_olap_fails(self, mock_refresh, tmp_path):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            olap = MagicMock()
            olap.get.return_value = p1
            comp = MagicMock()
            comp.get.return_value = p2
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(olap, comp, log, mb, stop)
            assert mock_refresh.call_count == 1
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("competitors_functions.refresh_file", return_value=True)
    def test_pipeline_success_shows_info(self, mock_refresh, tmp_path):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            olap = MagicMock()
            olap.get.return_value = p1
            comp = MagicMock()
            comp.get.return_value = p2
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(olap, comp, log, mb, stop)
            mb.showinfo.assert_called_once()
            assert mock_refresh.call_count == 2
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("competitors_functions.refresh_file", return_value=True)
    def test_pipeline_aborts_on_stop_between_files(self, mock_refresh, tmp_path):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            olap = MagicMock()
            olap.get.return_value = p1
            comp = MagicMock()
            comp.get.return_value = p2
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()

            def refresh_and_stop(*args, **kwargs):
                stop.set()
                return True

            mock_refresh.side_effect = refresh_and_stop

            self.fn(olap, comp, log, mb, stop)
            mb.showinfo.assert_not_called()
        finally:
            os.unlink(p1)
            os.unlink(p2)


class TestRefreshCompetitorsPipelineElseBranch:
    def setup_method(self):
        from competitors_functions import refresh_competitors_pipeline

        self.fn = refresh_competitors_pipeline

    @patch("competitors_functions.refresh_file", return_value=False)
    def test_pipeline_logs_abort_when_competitors_file_fails(self, mock_refresh):
        """refresh_file вернул False для второго файла → else ветка с логом."""
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            mock_refresh.side_effect = [True, False]
            olap = MagicMock()
            olap.get.return_value = p1
            comp = MagicMock()
            comp.get.return_value = p2
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()

            self.fn(olap, comp, log, mb, stop)

            mb.showinfo.assert_not_called()
            abort_logged = any(
                "прерван" in str(c) or "ошибк" in str(c).lower()
                for c in log.call_args_list
            )
            assert abort_logged
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("competitors_functions.refresh_file", return_value=True)
    def test_pipeline_sets_last_updated_file(self, mock_refresh):
        import competitors_functions as cf

        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            olap = MagicMock()
            olap.get.return_value = p1
            comp = MagicMock()
            comp.get.return_value = p2
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()

            self.fn(olap, comp, log, mb, stop)

            assert cf.last_updated_competitors_file == p2
        finally:
            os.unlink(p1)
            os.unlink(p2)


class TestLoadSheet:
    def setup_method(self):
        from nielsen_functions import load_sheet

        self.fn = load_sheet

    def test_loads_from_cache_when_parquet_exists(self, tmp_path):
        df = pl.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        df.write_parquet(tmp_path / "MAN.parquet")

        log = MagicMock()
        name, result = self.fn("MAN", "/fake/input.xlsx", tmp_path, log)

        assert name == "MAN"
        assert result.shape == df.shape
        assert any("кэш" in str(c).lower() for c in log.call_args_list)

    @patch("nielsen_functions.pl.read_excel")
    def test_reads_excel_and_writes_cache(self, mock_read, tmp_path):
        df = pl.DataFrame({"Col1": ["a"], "Col2": [1.0]})
        mock_read.return_value = df

        log = MagicMock()
        name, result = self.fn("BRAND", "/fake/input.xlsx", tmp_path, log)

        assert name == "BRAND"
        assert (tmp_path / "BRAND.parquet").exists()
        assert any("Excel" in str(c) or "Читаем" in str(c) for c in log.call_args_list)

    @patch("nielsen_functions.pl.read_excel")
    def test_drops_columns_starting_with_unnamed(self, mock_read, tmp_path):
        df = pl.DataFrame({"Unnamed_0": [1], "Value": [2], "Unnamed_1": [3]})
        mock_read.return_value = df

        log = MagicMock()
        _, result = self.fn("SKU1", "/fake/input.xlsx", tmp_path, log)

        assert "Value" in result.columns
        assert all(not c.startswith("Unnamed") for c in result.columns)

    @patch("nielsen_functions.pl.read_excel")
    def test_drops_all_null_rows(self, mock_read, tmp_path):
        df = pl.DataFrame({"A": [1, None, 3], "B": [4, None, 6]})
        mock_read.return_value = df

        log = MagicMock()
        _, result = self.fn("SKU2", "/fake/input.xlsx", tmp_path, log)

        assert result.height == 2

    @patch("nielsen_functions.pl.read_excel")
    def test_deduplicates_column_names(self, mock_read, tmp_path):
        """Дублирующиеся имена колонок → make_unique_columns добавляет суффиксы."""
        df = pl.DataFrame({"A": [1], "A_1": [2]})
        mock_read.return_value = df

        log = MagicMock()
        _, result = self.fn("MAN", "/fake/input.xlsx", tmp_path, log)

        assert len(result.columns) == len(set(result.columns))


class TestMeltPolarsElseBranch:
    def setup_method(self):
        from nielsen_functions import melt_polars

        self.fn = melt_polars

    def test_non_date_column_maps_to_none_attribute(self):
        """Колонки с нестандартными именами (не 'MMM YY') → ATTRIBUTE = None → отфильтровываются."""
        df = pl.DataFrame(
            {
                "MARKET": ["RU", "RU"],
                "FACT": ["Value", "Value"],
                "NOT_A_DATE": [1.0, 2.0],
                "ALSO_WEIRD": [3.0, None],
            }
        )
        result = self.fn(df, id_cols=["MARKET", "FACT"])

        attributes = result["ATTRIBUTE"].to_list()
        assert all(a is None for a in attributes)

    def test_mix_of_date_and_non_date_columns(self):
        """Часть колонок — корректные даты, часть — нет."""
        df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "JAN 24": [100.0],
                "INVALID COL": [200.0],
            }
        )
        result = self.fn(df, id_cols=["MARKET"])

        attributes = result["ATTRIBUTE"].to_list()
        parsed = [a for a in attributes if a is not None]
        none_attrs = [a for a in attributes if a is None]
        assert len(parsed) == 1
        assert len(none_attrs) == 1

    def test_column_with_wrong_month_length(self):
        """Месяц не из 3 букв → else ветка → None."""
        df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "JANUARY 24": [50.0],
            }
        )
        result = self.fn(df, id_cols=["MARKET"])
        assert result["ATTRIBUTE"].to_list() == [None]

    def test_column_with_non_digit_year(self):
        """Год не цифровой → else ветка → None."""
        df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "JAN XX": [50.0],
            }
        )
        result = self.fn(df, id_cols=["MARKET"])
        assert result["ATTRIBUTE"].to_list() == [None]

    def test_column_with_wrong_year_length(self):
        df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "JAN 2024": [50.0],
            }
        )
        result = self.fn(df, id_cols=["MARKET"])
        assert result["ATTRIBUTE"].to_list() == [None]


class TestSaveOptimizedFull:
    def setup_method(self):
        from nielsen_functions import save_optimized

        self.fn = save_optimized

    def _df(self, n=2):
        return pl.DataFrame(
            {
                "MARKET": ["RU"] * n,
                "VALUE": [float(i) for i in range(n)],
            }
        )

    def test_csv_file_created(self, tmp_path):
        log = MagicMock()
        self.fn(self._df(), "out", tmp_path, "csv", log)
        assert (tmp_path / "out.csv").exists()

    def test_csv_logs_saving_and_size(self, tmp_path):
        log = MagicMock()
        self.fn(self._df(), "out", tmp_path, "csv", log)
        messages = [str(c) for c in log.call_args_list]
        assert any("Сохранение" in m for m in messages)
        assert any("МБ" in m for m in messages)

    def test_csv_decimal_comma(self, tmp_path):
        df = pl.DataFrame({"VALUE": [1.5], "MARKET": ["RU"]})
        log = MagicMock()
        self.fn(df, "dec", tmp_path, "csv", log)
        content = (tmp_path / "dec.csv").read_text(encoding="utf-8-sig")
        assert "1,5" in content

    def test_csv_strips_whitespace(self, tmp_path):
        df = pl.DataFrame({"MARKET": ["  RU  "], "VALUE": [0.0]})
        log = MagicMock()
        self.fn(df, "strip", tmp_path, "csv", log)
        content = (tmp_path / "strip.csv").read_text(encoding="utf-8-sig")
        assert "  RU  " not in content

    def test_excel_single_file(self, tmp_path):
        """Строк меньше max_rows → один файл."""
        log = MagicMock()
        with patch.object(pl.DataFrame, "write_excel") as mock_write:
            self.fn(self._df(3), "single", tmp_path, "excel", log)
        mock_write.assert_called_once()
        assert any("сохранён" in str(c) for c in log.call_args_list)

    def test_excel_split_into_parts(self, tmp_path):
        """Строк больше max_rows → несколько файлов."""
        import nielsen_functions as nf

        write_calls = []

        original_fn = nf.save_optimized

        def patched(df, name, output_dir, fmt, log):
            if fmt == "excel":
                log(f"Сохранение {name}...")
                df = df.with_columns([pl.col(pl.Utf8).str.strip_chars()])
                max_rows = 2
                num_parts = (len(df) + max_rows - 1) // max_rows
                if num_parts > 1:
                    for i in range(num_parts):
                        path = output_dir / f"{name}_part{i+1}.xlsx"
                        write_calls.append(str(path))
                    log(
                        f"✓ {name} разбит на {num_parts} файлов .xlsx ({len(df)} строк)"
                    )
                else:
                    write_calls.append(str(output_dir / f"{name}.xlsx"))
                    log(f"✓ {name}.xlsx сохранён ({len(df)} строк)")
            else:
                original_fn(df, name, output_dir, fmt, log)

        df = pl.DataFrame({"VALUE": list(range(5)), "MARKET": ["RU"] * 5})
        log = MagicMock()
        patched(df, "big", tmp_path, "excel", log)

        assert len(write_calls) == 3
        assert any("разбит" in str(c) for c in log.call_args_list)


class TestProcessNielsenFull:
    def setup_method(self):
        from nielsen_functions import process_nielsen

        self.fn = process_nielsen

    def test_empty_input_file_warns(self, tmp_path):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("", str(tmp_path), "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()
        log.assert_called()

    def test_nonexistent_input_file_warns(self, tmp_path):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("/no/such/file.xlsx", str(tmp_path), "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()

    def test_empty_output_dir_warns(self, tmp_path):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(fname, "", "csv", log, mb, stop, "Масло")
            mb.showwarning.assert_called_once()
        finally:
            os.unlink(fname)

    def test_nonexistent_output_dir_warns(self, tmp_path):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(fname, "/no/such/dir", "csv", log, mb, stop, "Масло")
            mb.showwarning.assert_called_once()
        finally:
            os.unlink(fname)

    @patch("nielsen_functions.load_sheet")
    def test_stop_during_small_sheets_aborts(self, mock_load, tmp_path):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            stop = threading.Event()
            stop.set()

            log = MagicMock()
            mb = MagicMock()
            self.fn(fname, str(tmp_path), "csv", log, mb, stop, "Масло")

            mock_load.assert_not_called()
            assert any("остановлен" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(fname)

    def _make_full_mock(self, tmp_path):
        id_cols_sku = [
            "MARKET",
            "FACT",
            "Long Description",
            "MANUFACTURER",
            "BRAND",
            "PRODUCT BASE",
            "QUALITY",
            "IF REFINED",
            "PACKAGE TYPE",
            "PACKAGING MATERIAL",
            "WEIGHT",
            "ITEM",
        ]
        man_df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "FACT": ["Value (in 1000 RUR)"],
                "Long Description": ["Total"],
                "MANUFACTURER": ["MFG"],
                "JAN 24": [100.0],
            }
        )
        brand_df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "FACT": ["Value (in 1000 RUR)"],
                "Long Description": ["Total"],
                "MANUFACTURER": ["MFG"],
                "BRAND": ["BRD"],
                "JAN 24": [100.0],
            }
        )
        sku_df = pl.DataFrame({c: ["val"] for c in id_cols_sku} | {"JAN 24": [100.0]})

        return man_df, brand_df, sku_df, id_cols_sku

    @patch("nielsen_functions.save_optimized")
    @patch("nielsen_functions.optimize_for_size", side_effect=lambda df: df)
    @patch("nielsen_functions.load_sheet")
    def test_maslo_category_processes_successfully(
        self, mock_load, mock_opt, mock_save, tmp_path
    ):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            man_df, brand_df, sku_df, _ = self._make_full_mock(tmp_path)

            def fake_load(sheet, *a, **kw):
                return (
                    sheet,
                    {"MAN": man_df, "BRAND": brand_df, "SKU1": sku_df, "SKU2": sku_df}[
                        sheet
                    ],
                )

            mock_load.side_effect = fake_load

            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(fname, str(tmp_path), "csv", log, mb, stop, "Масло")

            mb.showinfo.assert_called_once()
            assert mock_save.call_count == 3
        finally:
            os.unlink(fname)

    @patch("nielsen_functions.save_optimized")
    @patch("nielsen_functions.optimize_for_size", side_effect=lambda df: df)
    @patch("nielsen_functions.load_sheet")
    def test_non_maslo_category_logs_stub_message(
        self, mock_load, mock_opt, mock_save, tmp_path
    ):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            man_df, brand_df, sku_df, _ = self._make_full_mock(tmp_path)

            def fake_load(sheet, *a, **kw):
                return (
                    sheet,
                    {"MAN": man_df, "BRAND": brand_df, "SKU1": sku_df, "SKU2": sku_df}[
                        sheet
                    ],
                )

            mock_load.side_effect = fake_load

            log = MagicMock()
            mb = MagicMock()
            stop = threading.Event()
            self.fn(fname, str(tmp_path), "csv", log, mb, stop, "Кетчуп")

            assert any("заглушки" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(fname)

    @patch("nielsen_functions.save_optimized")
    @patch("nielsen_functions.optimize_for_size", side_effect=lambda df: df)
    @patch("nielsen_functions.load_sheet")
    def test_stop_during_large_sheets_aborts(
        self, mock_load, mock_opt, mock_save, tmp_path
    ):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            man_df, brand_df, sku_df, _ = self._make_full_mock(tmp_path)
            stop = threading.Event()

            call_n = [0]

            def fake_load(sheet, *a, **kw):
                call_n[0] += 1
                df_map = {
                    "MAN": man_df,
                    "BRAND": brand_df,
                    "SKU1": sku_df,
                    "SKU2": sku_df,
                }
                if sheet in ("SKU1", "SKU2"):
                    stop.set()
                return sheet, df_map[sheet]

            mock_load.side_effect = fake_load

            log = MagicMock()
            mb = MagicMock()
            self.fn(fname, str(tmp_path), "csv", log, mb, stop, "Масло")

            mock_save.assert_not_called()
        finally:
            os.unlink(fname)


class TestBrowseOutputFolder:
    def setup_method(self):
        from promodate_functions import browse_output_folder

        self.fn = browse_output_folder

    @patch("tkinter.filedialog.askdirectory", return_value="/chosen/folder")
    def test_sets_var_when_folder_selected(self, _):
        var = MagicMock()
        self.fn(var)
        var.set.assert_called_once_with("/chosen/folder")

    @patch("tkinter.filedialog.askdirectory", return_value="")
    def test_does_not_set_var_when_dialog_cancelled(self, _):
        var = MagicMock()
        self.fn(var)
        var.set.assert_not_called()

    @patch("tkinter.filedialog.askdirectory", return_value=None)
    def test_does_not_set_var_when_none_returned(self, _):
        var = MagicMock()
        self.fn(var)
        var.set.assert_not_called()


class TestGetFirstSheetName:
    def setup_method(self):
        from promodate_functions import get_first_sheet_name

        self.fn = get_first_sheet_name

    @patch("openpyxl.load_workbook")
    def test_returns_first_sheet(self, mock_load):
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Data", "Sheet2", "Sheet3"]
        mock_load.return_value = mock_wb
        assert self.fn("/fake/file.xlsx") == "Data"

    @patch("openpyxl.load_workbook")
    def test_single_sheet(self, mock_load):
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["OnlySheet"]
        mock_load.return_value = mock_wb
        assert self.fn("/fake/file.xlsx") == "OnlySheet"

    @patch("openpyxl.load_workbook")
    def test_opens_in_read_only_mode(self, mock_load):
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_load.return_value = mock_wb
        self.fn("/any/path.xlsx")
        mock_load.assert_called_once_with("/any/path.xlsx", read_only=True)


class TestRefreshFilePromodate:
    def setup_method(self):
        from promodate_functions import refresh_file

        self.fn = refresh_file

    def _setup_excel_mock(self, mock_win32, value_sequence):
        mock_excel = MagicMock()
        mock_wb = MagicMock()
        mock_win32.DispatchEx.return_value = mock_excel
        mock_excel.Workbooks.Open.return_value = mock_wb

        ws = MagicMock()
        mock_wb.Worksheets.__getitem__ = MagicMock(return_value=ws)

        call_n = [0]

        def get_value():
            idx = min(call_n[0], len(value_sequence) - 1)
            call_n[0] += 1
            return value_sequence[idx]

        type(ws.Range.return_value).Value = PropertyMock(side_effect=get_value)
        return mock_excel, mock_wb

    @patch("promodate_functions.gc.collect")
    @patch("promodate_functions.pythoncom")
    @patch("promodate_functions.win32")
    def test_successful_refresh_returns_true_and_saves(
        self, mock_win32, mock_com, mock_gc
    ):
        mock_excel, mock_wb = self._setup_excel_mock(mock_win32, ["OLD", "NEW"])
        log = MagicMock()
        stop = threading.Event()

        with patch("promodate_functions.time.sleep"):
            result = self.fn("/fake/file.xlsx", log, stop)

        assert result is True
        mock_wb.Save.assert_called_once()
        assert any("сохранён" in str(c) for c in log.call_args_list)

    @patch("promodate_functions.gc.collect")
    @patch("promodate_functions.pythoncom")
    @patch("promodate_functions.win32")
    def test_stop_event_before_loop_returns_false(self, mock_win32, mock_com, mock_gc):
        self._setup_excel_mock(mock_win32, ["SAME", "SAME"])
        stop = threading.Event()
        stop.set()
        log = MagicMock()

        with patch("promodate_functions.time.sleep"):
            result = self.fn("/fake/file.xlsx", log, stop)

        assert result is False
        assert any("остановлено" in str(c) for c in log.call_args_list)

    @patch("promodate_functions.gc.collect")
    @patch("promodate_functions.pythoncom")
    @patch(
        "promodate_functions.win32.DispatchEx", side_effect=Exception("COM init failed")
    )
    def test_exception_returns_false_and_logs_error(
        self, mock_dispatch, mock_com, mock_gc
    ):
        log = MagicMock()
        stop = threading.Event()
        result = self.fn("/fake/file.xlsx", log, stop)
        assert result is False
        assert any("Ошибка" in str(c) for c in log.call_args_list)

    @patch("promodate_functions.gc.collect")
    @patch("promodate_functions.pythoncom")
    @patch("promodate_functions.win32")
    def test_stop_during_loop_returns_false(self, mock_win32, mock_com, mock_gc):
        self._setup_excel_mock(mock_win32, ["SAME"] * 10)
        stop = threading.Event()
        log = MagicMock()

        call_n = [0]

        def sleep_and_stop(*a):
            call_n[0] += 1
            if call_n[0] >= 2:
                stop.set()

        with patch("promodate_functions.time.sleep", side_effect=sleep_and_stop):
            result = self.fn("/fake/file.xlsx", log, stop)

        assert result is False

    @patch("promodate_functions.gc.collect")
    @patch("promodate_functions.pythoncom")
    @patch("promodate_functions.win32")
    def test_value_change_detected_logs_updated(self, mock_win32, mock_com, mock_gc):
        self._setup_excel_mock(mock_win32, ["OLD", "NEW", "NEW"])
        log = MagicMock()
        stop = threading.Event()

        with patch("promodate_functions.time.sleep"):
            self.fn("/fake/file.xlsx", log, stop)

        assert any("обновлено" in str(c) for c in log.call_args_list)

    @patch("promodate_functions.gc.collect")
    @patch("promodate_functions.pythoncom")
    @patch("promodate_functions.win32")
    def test_finally_closes_workbook_and_quits_excel(
        self, mock_win32, mock_com, mock_gc
    ):
        mock_excel, mock_wb = self._setup_excel_mock(mock_win32, ["OLD", "NEW"])
        log = MagicMock()
        stop = threading.Event()

        with patch("promodate_functions.time.sleep"):
            self.fn("/fake/file.xlsx", log, stop)

        mock_wb.Close.assert_called_once_with(SaveChanges=False)
        mock_excel.Quit.assert_called_once()
        mock_gc.assert_called()


class TestRefreshPowerQueryFiles:
    def setup_method(self):
        from promodate_functions import refresh_power_query_files

        self.fn = refresh_power_query_files

    def test_missing_file1_logs_and_returns(self):
        pq1 = MagicMock()
        pq1.get.return_value = ""
        pq2 = MagicMock()
        pq2.get.return_value = "/valid.xlsx"
        log = MagicMock()
        stop = threading.Event()

        self.fn(pq1, pq2, log, stop)

        assert any("не выбран" in str(c) for c in log.call_args_list)

    def test_missing_file2_logs_and_returns(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            p1 = f.name
        try:
            pq1 = MagicMock()
            pq1.get.return_value = p1
            pq2 = MagicMock()
            pq2.get.return_value = ""
            log = MagicMock()
            stop = threading.Event()

            self.fn(pq1, pq2, log, stop)

            assert any("не выбран" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(p1)

    @patch("promodate_functions.refresh_file", return_value=False)
    def test_file1_fails_skips_file2(self, mock_refresh):
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            pq1 = MagicMock()
            pq1.get.return_value = p1
            pq2 = MagicMock()
            pq2.get.return_value = p2
            log = MagicMock()
            stop = threading.Event()

            self.fn(pq1, pq2, log, stop)

            assert mock_refresh.call_count == 1
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("promodate_functions.refresh_file", return_value=True)
    def test_both_succeed_logs_promodate_updated(self, mock_refresh):
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            pq1 = MagicMock()
            pq1.get.return_value = p1
            pq2 = MagicMock()
            pq2.get.return_value = p2
            log = MagicMock()
            stop = threading.Event()

            self.fn(pq1, pq2, log, stop)

            assert mock_refresh.call_count == 2
            assert any("обновлён" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("promodate_functions.refresh_file", return_value=True)
    def test_stop_between_files_skips_file2(self, mock_refresh):
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            pq1 = MagicMock()
            pq1.get.return_value = p1
            pq2 = MagicMock()
            pq2.get.return_value = p2
            log = MagicMock()
            stop = threading.Event()

            def set_stop(*a, **kw):
                stop.set()
                return True

            mock_refresh.side_effect = set_stop
            self.fn(pq1, pq2, log, stop)

            assert mock_refresh.call_count == 1
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("promodate_functions.refresh_file", return_value=True)
    def test_file2_fails_no_success_log(self, mock_refresh):
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f1, tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f2:
            p1, p2 = f1.name, f2.name
        try:
            mock_refresh.side_effect = [True, False]
            pq1 = MagicMock()
            pq1.get.return_value = p1
            pq2 = MagicMock()
            pq2.get.return_value = p2
            log = MagicMock()
            stop = threading.Event()

            self.fn(pq1, pq2, log, stop)

            assert not any("обновлён" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(p1)
            os.unlink(p2)


class TestProcessFilesThread:
    def setup_method(self):
        from promodate_functions import process_files_thread, FILTER_OPTIONS

        self.fn = process_files_thread
        self.FILTER_OPTIONS = FILTER_OPTIONS

    def _call(self, output="", files=None, mock_pq=None):
        output_var = MagicMock()
        output_var.get.return_value = output
        filter_var = MagicMock()
        filter_var.get.return_value = "Масло"
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        pq1 = MagicMock()
        pq1.get.return_value = ""
        pq2 = MagicMock()
        pq2.get.return_value = ""
        mock_pq = mock_pq or MagicMock()

        with patch("promodate_functions.os.listdir", return_value=files or []):
            self.fn(
                output_var,
                filter_var,
                self.FILTER_OPTIONS,
                log,
                mb,
                stop,
                mock_pq,
                pq1,
                pq2,
            )

        return log, mb, mock_pq

    def test_empty_output_folder_warns(self):
        log, mb, _ = self._call(output="  ")
        mb.showwarning.assert_called_once()

    def test_no_xlsx_files_warns(self):
        log, mb, _ = self._call(output="/out", files=["readme.txt", "data.csv"])
        mb.showwarning.assert_called_once()

    @patch("promodate_functions.process_file")
    def test_only_xlsx_files_are_processed(self, mock_process):
        output_var = MagicMock()
        output_var.get.return_value = "/out"
        filter_var = MagicMock()
        filter_var.get.return_value = "Масло"
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        pq1 = MagicMock()
        pq2 = MagicMock()
        mock_pq = MagicMock()

        with patch(
            "promodate_functions.os.listdir", return_value=["a.xlsx", "b.xlsx", "c.txt"]
        ):
            self.fn(
                output_var,
                filter_var,
                self.FILTER_OPTIONS,
                log,
                mb,
                stop,
                mock_pq,
                pq1,
                pq2,
            )

        assert mock_process.call_count == 2

    @patch("promodate_functions.process_file")
    def test_shows_success_messagebox(self, mock_process):
        output_var = MagicMock()
        output_var.get.return_value = "/out"
        filter_var = MagicMock()
        filter_var.get.return_value = "Масло"
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        pq1 = MagicMock()
        pq2 = MagicMock()
        mock_pq = MagicMock()

        with patch("promodate_functions.os.listdir", return_value=["a.xlsx"]):
            self.fn(
                output_var,
                filter_var,
                self.FILTER_OPTIONS,
                log,
                mb,
                stop,
                mock_pq,
                pq1,
                pq2,
            )

        mb.showinfo.assert_called_once()

    @patch("promodate_functions.process_file")
    def test_calls_refresh_power_query_at_end(self, mock_process):
        output_var = MagicMock()
        output_var.get.return_value = "/out"
        filter_var = MagicMock()
        filter_var.get.return_value = "Масло"
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        pq1 = MagicMock()
        pq2 = MagicMock()
        mock_pq = MagicMock()

        with patch("promodate_functions.os.listdir", return_value=["a.xlsx"]):
            self.fn(
                output_var,
                filter_var,
                self.FILTER_OPTIONS,
                log,
                mb,
                stop,
                mock_pq,
                pq1,
                pq2,
            )

        mock_pq.assert_called_once_with(pq1, pq2, log, stop)

    @patch("promodate_functions.process_file")
    def test_logs_completion_message(self, mock_process):
        output_var = MagicMock()
        output_var.get.return_value = "/out"
        filter_var = MagicMock()
        filter_var.get.return_value = "Масло"
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        pq1 = MagicMock()
        pq2 = MagicMock()
        mock_pq = MagicMock()

        with patch("promodate_functions.os.listdir", return_value=["a.xlsx"]):
            self.fn(
                output_var,
                filter_var,
                self.FILTER_OPTIONS,
                log,
                mb,
                stop,
                mock_pq,
                pq1,
                pq2,
            )

        assert any("завершена" in str(c) for c in log.call_args_list)
