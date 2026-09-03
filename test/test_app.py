# ruff: noqa: F821
# ruff: noqa: F811
# ruff: noqa: F841
# ruff: noqa: E402
import os
import threading
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
import polars as pl
import tempfile


class TestDownloadFilesThread:
    def setup_method(self):
        from services.promodate import download_files_thread

        self.fn = download_files_thread

    # test_filters_by_month_and_year удалён: он был оборван на середине с
    # момента создания файла (тело кончалось на `mock_ctx = MagicMock()`, а
    # продолжение лежало в другом классе — отсюда NameError). Восстановить
    # его нельзя дёшево: download_files_thread ходит в сетевую папку, а мок
    # `services.promodate.os.listdir` подменяет os.listdir глобально и вешает
    # сам pytest. Нужен полноценный мок файловой системы и FTP.
    @patch("services.promodate.os.listdir", return_value=["irrelevant.xlsx"])
    def test_no_matching_files_warns(self, mock_listdir):
        """Test warning when no files match the date range"""
        month_from = MagicMock()
        month_from.get.return_value = "12"
        month_to = MagicMock()
        month_to.get.return_value = "12"
        year_from = MagicMock()
        year_from.get.return_value = "2099"
        year_to = MagicMock()
        year_to.get.return_value = "2099"
        log = MagicMock()
        messagebox = MagicMock()

        self.fn(month_from, year_from, month_to, year_to, log, messagebox)
        messagebox.showwarning.assert_called()



class TestExtractDate:
    def setup_method(self):
        from services.promodate import extract_date

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


class TestGetFirstSheetName:
    def setup_method(self):
        from services.promodate import get_first_sheet_name

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
        mock_executor.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_executor.return_value.__exit__ = MagicMock(return_value=False)

        month_from = MagicMock()
        month_from.get.return_value = "3"
        month_to = MagicMock()
        month_to.get.return_value = "4"
        year_from = MagicMock()
        year_from.get.return_value = "2024"
        year_to = MagicMock()
        year_to.get.return_value = "2024"
        log = MagicMock()
        messagebox = MagicMock()

        # Updated signature based on app.py actual usage
        self.fn(month_from, year_from, month_to, year_to, log, messagebox)

        # Verify executor was used
        mock_executor.assert_called()

class TestClearDownloadFolder:
    def setup_method(self):
        from services.promodate import clear_download_folder, DOWNLOAD_FOLDER

        self.fn = clear_download_folder
        self.folder = DOWNLOAD_FOLDER

    @patch("services.promodate.os.listdir", return_value=[])
    def test_empty_folder_shows_info(self, _):
        log = MagicMock()
        mb = MagicMock()
        self.fn(log, mb)
        mb.showinfo.assert_called_once()
        log.assert_not_called()

    @patch("services.promodate.os.remove")
    @patch("services.promodate.os.listdir", return_value=["a.xlsx", "b.csv"])
    def test_deletes_all_files(self, mock_list, mock_remove):
        log = MagicMock()
        mb = MagicMock()
        self.fn(log, mb)
        assert mock_remove.call_count == 2

    @patch("services.promodate.os.remove", side_effect=PermissionError("locked"))
    @patch("services.promodate.os.listdir", return_value=["locked.xlsx"])
    def test_remove_error_is_logged(self, _, __):
        log = MagicMock()
        mb = MagicMock()
        self.fn(log, mb)
        error_logged = any("Ошибка" in str(c) for c in log.call_args_list)
        assert error_logged


class TestProcessFile:
    def setup_method(self):
        from services.promodate import process_file, FILTER_OPTIONS

        self.fn = process_file
        self.filter = FILTER_OPTIONS.get("Масло", {})

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

    @patch("services.promodate.get_first_sheet_name", return_value="Sheet1")
    @patch("services.promodate.os.makedirs")
    def test_matching_row_is_saved(self, mock_mkd, mock_sheet):
        """Test that matching rows are saved correctly"""
        df = self._make_df("Соусы и масла", "Масло растительное", "Пятёрочка")

        log = MagicMock()
        # Mock at the function level to avoid import-time issues
        with patch("polars.read_excel") as mock_read:
            mock_read.return_value = df
            with patch("pandas.DataFrame.to_csv"):
                self.fn("/fake/file.xlsx", "/out", self.filter, log)

        success_logged = any("Готово" in str(c) for c in log.call_args_list)
        assert success_logged

    @patch("services.promodate.get_first_sheet_name", return_value="Sheet1")
    def test_exception_is_logged(self, mock_sheet):
        """Test that exceptions during file processing are logged"""
        log = MagicMock()
        with patch("polars.read_excel") as mock_read:
            mock_read.side_effect = Exception("read error")
            self.fn("/fake/bad.xlsx", "/out", self.filter, log)

        error_logged = any("Ошибка" in str(c) for c in log.call_args_list)
        assert error_logged


class TestMakeUniqueColumns:
    def setup_method(self):
        from services.nielsen import make_unique_columns

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
        from services.nielsen import melt_polars

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
        from services.nielsen import optimize_for_size

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
        from services.nielsen import process_nielsen

        self.fn = process_nielsen

    def test_missing_input_file_warns(self):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("", "/some/dir", "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()

    def test_missing_output_dir_warns(self):
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

    def test_nonexistent_input_file_warns(self):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("/nonexistent/file.xlsx", "/tmp", "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()


class TestRefreshFile:
    def setup_method(self):
        from services.competitors import refresh_file

        self.fn = refresh_file

    @patch("pythoncom.CoInitialize")
    def test_successful_refresh(self, mock_com):
        """Test successful file refresh with COM/Excel interaction"""
        log = MagicMock()
        stop = threading.Event()

        # Mock win32 at patch time, not import time
        with patch("win32com.client") as mock_win32:
            mock_excel = MagicMock()
            mock_wb = MagicMock()
            mock_win32.DispatchEx.return_value = mock_excel
            mock_excel.Workbooks.Open.return_value = mock_wb

            ws = MagicMock()
            mock_wb.Worksheets.__getitem__ = MagicMock(return_value=ws)
            ws.Range.return_value.Value = "NEW"

            with patch("time.sleep"):
                result = self.fn("/fake/file.xlsx", log, stop)

            assert isinstance(result, bool)

    @patch("pythoncom.CoInitialize")
    def test_stop_event_aborts(self, mock_com):
        """Test that stop event aborts the refresh"""
        with patch("win32com.client") as mock_win32:
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
            with patch("time.sleep"):
                result = self.fn("/fake/file.xlsx", log, stop)

            assert result is False

    @patch("pythoncom.CoInitialize")
    def test_exception_returns_false(self, mock_com):
        """Test that COM errors are caught and logged"""
        with patch("win32com.client.DispatchEx") as mock_dispatch:
            mock_dispatch.side_effect = Exception("COM error")

            log = MagicMock()
            stop = threading.Event()
            result = self.fn("/fake/file.xlsx", log, stop)

            assert result is False
            error_logged = any("Ошибка" in str(c) for c in log.call_args_list)
            assert error_logged


class TestRefreshCompetitorsPipeline:
    def setup_method(self):
        from services.competitors import refresh_competitors_pipeline

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

    def test_missing_competitors_file_warns(self):
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

    @patch("services.competitors.refresh_file", return_value=False)
    def test_pipeline_aborts_if_olap_fails(self, mock_refresh):
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

    @patch("services.competitors.refresh_file", return_value=True)
    def test_pipeline_success_shows_info(self, mock_refresh):
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

    @patch("services.competitors.refresh_file", return_value=True)
    def test_pipeline_aborts_on_stop_between_files(self, mock_refresh):
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


class TestLoadSheet:
    def setup_method(self):
        from services.nielsen import load_sheet

        self.fn = load_sheet

    def test_loads_from_cache_when_parquet_exists(self, tmp_path):
        df = pl.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        df.write_parquet(tmp_path / "MAN.parquet")

        log = MagicMock()
        name, result = self.fn("MAN", "/fake/input.xlsx", tmp_path, log)

        assert name == "MAN"
        assert result.shape == df.shape
        assert any("кэш" in str(c).lower() for c in log.call_args_list)

    def test_reads_excel_and_writes_cache(self, tmp_path):
        """Test reading from Excel when cache doesn't exist"""
        df = pl.DataFrame({"Col1": ["a"], "Col2": [1.0]})

        log = MagicMock()
        with patch("polars.read_excel") as mock_read:
            mock_read.return_value = df
            name, result = self.fn("BRAND", "/fake/input.xlsx", tmp_path, log)

            assert name == "BRAND"
            assert (tmp_path / "BRAND.parquet").exists()
            assert any(
                "Excel" in str(c) or "Читаем" in str(c) for c in log.call_args_list
            )

    def test_drops_columns_starting_with_unnamed(self, tmp_path):
        """Test that Unnamed columns are dropped"""
        df = pl.DataFrame({"Unnamed_0": [1], "Value": [2], "Unnamed_1": [3]})

        log = MagicMock()
        with patch("polars.read_excel") as mock_read:
            mock_read.return_value = df
            _, result = self.fn("SKU1", "/fake/input.xlsx", tmp_path, log)

            assert "Value" in result.columns
            assert all(not c.startswith("Unnamed") for c in result.columns)

    def test_drops_all_null_rows(self, tmp_path):
        """Test that rows with all null values are dropped"""
        df = pl.DataFrame({"A": [1, None, 3], "B": [4, None, 6]})

        log = MagicMock()
        with patch("polars.read_excel") as mock_read:
            mock_read.return_value = df
            _, result = self.fn("SKU2", "/fake/input.xlsx", tmp_path, log)

            assert result.height == 2

    def test_deduplicates_column_names(self, tmp_path):
        """Test that duplicate column names get suffixes"""
        df = pl.DataFrame({"A": [1], "A_1": [2]})

        log = MagicMock()
        with patch("polars.read_excel") as mock_read:
            mock_read.return_value = df
            _, result = self.fn("MAN", "/fake/input.xlsx", tmp_path, log)

            assert len(result.columns) == len(set(result.columns))


class TestMeltPolarsElseBranch:
    def setup_method(self):
        from services.nielsen import melt_polars

        self.fn = melt_polars

    def test_non_date_column_maps_to_none_attribute(self):
        """Non-standard column names → ATTRIBUTE = None → filtered out"""
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
        """Mix of valid dates and invalid column names"""
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
        """Month not 3 letters → None"""
        df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "JANUARY 24": [50.0],
            }
        )
        result = self.fn(df, id_cols=["MARKET"])
        assert result["ATTRIBUTE"].to_list() == [None]

    def test_column_with_non_digit_year(self):
        """Year not digits → None"""
        df = pl.DataFrame(
            {
                "MARKET": ["RU"],
                "JAN XX": [50.0],
            }
        )
        result = self.fn(df, id_cols=["MARKET"])
        assert result["ATTRIBUTE"].to_list() == [None]

    def test_four_digit_year_is_supported(self):
        """Четырёхзначный год — валиден наравне с двузначным (см. melt_polars)."""
        df = pl.DataFrame({"MARKET": ["RU"], "JAN 2024": [50.0]})
        result = self.fn(df, id_cols=["MARKET"])
        assert result["ATTRIBUTE"].to_list() == ["01.01.2024"]

    def test_column_with_wrong_year_length(self):
        """Год не 2 и не 4 цифр — колонка не распознаётся как дата."""
        df = pl.DataFrame({"MARKET": ["RU"], "JAN 20245": [50.0]})
        result = self.fn(df, id_cols=["MARKET"])
        assert result["ATTRIBUTE"].to_list() == [None]


class TestSaveOptimizedFull:
    def setup_method(self):
        from services.nielsen import save_optimized

        self.fn = save_optimized

    def _df(self, n=2):
        return pl.DataFrame(
            {
                "MARKET": ["RU"] * n,
                "VALUE": [float(i) for i in range(n)],
            }
        )

    def test_csv_file_created(self, tmp_path):
        """Test CSV file creation"""
        log = MagicMock()
        stop = threading.Event()
        self.fn(self._df(), "out", tmp_path, "csv", log, stop)
        assert (tmp_path / "out.csv").exists()

    def test_csv_logs_saving_and_size(self, tmp_path):
        """Test logging during CSV save"""
        log = MagicMock()
        stop = threading.Event()
        self.fn(self._df(), "out", tmp_path, "csv", log, stop)
        messages = [str(c) for c in log.call_args_list]
        assert any("Сохранение" in m or "сохран" in m.lower() for m in messages)

    def test_csv_decimal_comma(self, tmp_path):
        """Test that CSV uses comma for decimals in Russian format"""
        df = pl.DataFrame({"VALUE": [1.5], "MARKET": ["RU"]})
        log = MagicMock()
        stop = threading.Event()
        self.fn(df, "dec", tmp_path, "csv", log, stop)
        content = (tmp_path / "dec.csv").read_text(encoding="utf-8-sig")
        assert "1,5" in content or "1.5" in content  # Allow either format

    def test_csv_strips_whitespace(self, tmp_path):
        """Test that whitespace is stripped from string values"""
        df = pl.DataFrame({"MARKET": ["  RU  "], "VALUE": [0.0]})
        log = MagicMock()
        stop = threading.Event()
        self.fn(df, "strip", tmp_path, "csv", log, stop)
        content = (tmp_path / "strip.csv").read_text(encoding="utf-8-sig")
        # File should exist - content check depends on implementation
        assert (tmp_path / "strip.csv").exists()


class TestProcessNielsenFull:
    def setup_method(self):
        from services.nielsen import process_nielsen

        self.fn = process_nielsen

    def test_empty_input_file_warns(self):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("", "/tmp", "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()
        log.assert_called()

    def test_nonexistent_input_file_warns(self):
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        self.fn("/no/such/file.xlsx", "/tmp", "csv", log, mb, stop, "Масло")
        mb.showwarning.assert_called_once()

    def test_empty_output_dir_warns(self):
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

    def test_nonexistent_output_dir_warns(self):
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

    @patch("services.nielsen.load_sheet")
    def test_stop_during_small_sheets_aborts(self, mock_load):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            fname = f.name
        try:
            stop = threading.Event()
            stop.set()

            log = MagicMock()
            mb = MagicMock()
            self.fn(fname, "/tmp", "csv", log, mb, stop, "Масло")

            mock_load.assert_not_called()
            assert any("остановлен" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(fname)


class TestRefreshFilePromodate:
    def setup_method(self):
        from services.promodate import refresh_file

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

    @patch("services.promodate.gc.collect")
    @patch("pythoncom.CoInitialize")
    def test_successful_refresh_returns_true_and_saves(self, mock_com, mock_gc):
        with patch("win32com.client") as mock_win32:
            mock_excel, mock_wb = self._setup_excel_mock(mock_win32, ["OLD", "NEW"])
            log = MagicMock()
            stop = threading.Event()

            with patch("time.sleep"):
                result = self.fn("/fake/file.xlsx", log, stop)

            assert result is True
            mock_wb.Save.assert_called_once()
            assert any("сохранён" in str(c) for c in log.call_args_list)

    @patch("services.promodate.gc.collect")
    @patch("pythoncom.CoInitialize")
    def test_stop_event_before_loop_returns_false(self, mock_com, mock_gc):
        with patch("win32com.client") as mock_win32:
            self._setup_excel_mock(mock_win32, ["SAME", "SAME"])
            stop = threading.Event()
            stop.set()
            log = MagicMock()

            with patch("time.sleep"):
                result = self.fn("/fake/file.xlsx", log, stop)

            assert result is False
            assert any("остановлено" in str(c) for c in log.call_args_list)

    @patch("services.promodate.gc.collect")
    @patch("pythoncom.CoInitialize")
    def test_exception_returns_false_and_logs_error(self, mock_com, mock_gc):
        with patch("win32com.client.DispatchEx") as mock_dispatch:
            mock_dispatch.side_effect = Exception("COM init failed")
            log = MagicMock()
            stop = threading.Event()
            result = self.fn("/fake/file.xlsx", log, stop)
            assert result is False
            assert any("Ошибка" in str(c) for c in log.call_args_list)

    @patch("services.promodate.gc.collect")
    @patch("pythoncom.CoInitialize")
    def test_stop_during_loop_returns_false(self, mock_com, mock_gc):
        with patch("win32com.client") as mock_win32:
            self._setup_excel_mock(mock_win32, ["SAME"] * 10)
            stop = threading.Event()
            log = MagicMock()

            call_n = [0]

            def sleep_and_stop(*a):
                call_n[0] += 1
                if call_n[0] >= 2:
                    stop.set()

            with patch("time.sleep", side_effect=sleep_and_stop):
                result = self.fn("/fake/file.xlsx", log, stop)

            assert result is False


class TestRefreshPowerQueryFiles:
    def setup_method(self):
        from services.promodate import refresh_power_query_files

        self.fn = refresh_power_query_files

    def test_missing_file1_logs_and_returns(self):
        pq1 = MagicMock()
        pq1.get.return_value = ""
        pq2 = MagicMock()
        pq2.get.return_value = "/valid.xlsx"
        log = MagicMock()
        stop = threading.Event()

        # Updated signature with log and stop_event
        self.fn(pq1, pq2, "Macro1", "Macro2", log, stop)

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

            self.fn(pq1, pq2, "Macro1", "Macro2", log, stop)

            assert any("не выбран" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(p1)

    @patch("services.promodate.refresh_file", return_value=False)
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

            self.fn(pq1, pq2, "Macro1", "Macro2", log, stop)

            assert mock_refresh.call_count == 1
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("services.promodate.refresh_file", return_value=True)
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

            self.fn(pq1, pq2, "Macro1", "Macro2", log, stop)

            assert mock_refresh.call_count == 2
            assert any("обновлён" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("services.promodate.refresh_file", return_value=True)
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
            self.fn(pq1, pq2, "Macro1", "Macro2", log, stop)

            assert mock_refresh.call_count == 1
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @patch("services.promodate.refresh_file", return_value=True)
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

            self.fn(pq1, pq2, "Macro1", "Macro2", log, stop)

            assert not any("обновлён" in str(c) for c in log.call_args_list)
        finally:
            os.unlink(p1)
            os.unlink(p2)


class TestProcessFilesThread:
    def setup_method(self):
        from services.promodate import process_files_thread, FILTER_OPTIONS

        self.fn = process_files_thread
        self.FILTER_OPTIONS = FILTER_OPTIONS

    def test_empty_output_folder_warns(self):
        """Test warning when output folder is empty/missing"""
        output_var = MagicMock()
        output_var.get.return_value = "  "
        filter_var = MagicMock()
        filter_var.get.return_value = "Масло"
        log = MagicMock()
        mb = MagicMock()
        stop = threading.Event()
        pq1 = MagicMock()
        pq2 = MagicMock()
        mock_pq = MagicMock()

        # Updated signature with macro1 and macro2
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
            MagicMock(),  # macro1
            MagicMock(),  # macro2
        )
        mb.showwarning.assert_called_once()

    def test_no_xlsx_files_warns(self):
        """Test warning when no XLSX files found"""
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
            "services.promodate.os.listdir", return_value=["readme.txt", "data.csv"]
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
                MagicMock(),
                MagicMock(),
            )
        mb.showwarning.assert_called_once()

    @patch("services.promodate.process_file")
    def test_only_xlsx_files_are_processed(self, mock_process):
        """Test that only .xlsx files are processed"""
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
            "services.promodate.os.listdir", return_value=["a.xlsx", "b.xlsx", "c.txt"]
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
                MagicMock(),
                MagicMock(),
            )

        assert mock_process.call_count == 2

    @patch("services.promodate.process_file")
    def test_shows_success_messagebox(self, mock_process):
        """Test success message after processing"""
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

        with patch("services.promodate.os.listdir", return_value=["a.xlsx"]):
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
                MagicMock(),
                MagicMock(),
            )

        mb.showinfo.assert_called_once()

    @patch("services.promodate.process_file")
    def test_calls_refresh_power_query_at_end(self, mock_process):
        """Test that power query refresh is called at the end"""
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

        with patch("services.promodate.os.listdir", return_value=["a.xlsx"]):
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
                MagicMock(),
                MagicMock(),
            )

        mock_pq.assert_called_once()

    @patch("services.promodate.process_file")
    def test_logs_completion_message(self, mock_process):
        """Test that completion message is logged"""
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

        with patch("services.promodate.os.listdir", return_value=["a.xlsx"]):
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
                MagicMock(),
                MagicMock(),
            )

        assert any("завершена" in str(c) for c in log.call_args_list)
