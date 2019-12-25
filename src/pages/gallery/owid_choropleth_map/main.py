"""In this example we show how to construct an interactive
[Choropleth](ps://en.wikipedia.org/wiki/Choropleth_map) map.

The example is inspired by the article
[Choropleth maps with geopandas, Bokeh and Panel]\
(https://dmnfarrell.github.io/bioinformatics/bokeh-maps)
by [Damian Farrell](https://github.com/dmnfarrell). See also his
[Notebook](https://github.com/dmnfarrell/teaching/blob/master/geo/maps_python.ipynb)

The data is provided by [Our World in Data](https://ourworldindata.org/). You can find the source
data on [GitHub](https://github.com/owid/owid-datasets/tree/master/datasets).

This example uses [geopandas](http://geopandas.org/). If you wan't to `pip install geopandas` on
Windows then please follow the
[using-geopandas-windows](https://geoffboeing.com/2014/09/using-geopandas-windows/) article.
"""

import json
import pathlib
from functools import lru_cache
from typing import Optional

import geopandas as gpd
import pandas as pd
import panel as pn
import panel.widgets as pnw
from bokeh.models import ColorBar, GeoJSONDataSource, LinearColorMapper
from bokeh.palettes import brewer  # pylint: disable=no-name-in-module
from bokeh.plotting import figure
import param

FILE_DIR = pathlib.Path(__file__).parent
SHAPEFILE = FILE_DIR / "data/ne_110m_admin_0_countries.shp"
OWIDDATASETS_FILE = FILE_DIR / "data/owid_datasets.csv"


class OwidDashboard(param.Parameterized):
    """A Dashboard showing the Owid World Data like 'Annual CO2 Emissions'

        Args:
            shape_data (Optional[gpd.geodataframe.GeoDataFrame], optional): The Map shape data.
            Defaults to None.
            owid_data_sets (Optional[pd.DataFrame], optional): A DataFrame listing the available
            datasets. Defaults to None.
    """

    dataset_name = param.ObjectSelector()
    year = param.Integer(2010, bounds=(1950, 2018))

    def __init__(
        self,
        shape_data: Optional[gpd.geodataframe.GeoDataFrame] = None,
        owid_data_sets: Optional[pd.DataFrame] = None,
    ):
        if not shape_data:
            self.shape_data = self.get_shape_data()
        else:
            self.shape_data = shape_data

        if not owid_data_sets:
            self.owid_data_sets = self.get_owid_data_sets()
        else:
            self.owid_data_sets = owid_data_sets

        dataset_names = list(self.owid_data_sets.index)
        self.param.dataset_name.objects = dataset_names
        self.param.dataset_name.default = dataset_names[0]

    @param.depends("dataset_name", "year")
    def map_plot(self):
        return self._map_plot(self.dataset_name, self.year)

    @param.depends("dataset_name")
    def download_link(self):
        download_icon = '<img src="https://www.google.com/url?sa=i&source=images&cd=&ved=2ahUKEwiJjIndjdDmAhXOY1AKHQasC20QjRx6BAgBEAQ&url=https%3A%2F%2Fwww.flaticon.com%2Ffree-icon%2Fdownload-button_532&psig=AOvVaw2xuzJjaLznTZ6nFo2696u-&ust=1577339513551859"/>'
        return f'<a href="{self.owid_data_sets.loc[self.dataset_name].url}" download>{download_icon}</a>'


    @lru_cache(2048)
    def _map_plot(self, name: str, year: int):
        shape_data, key = self.get_owid_data(
            self.owid_data_sets, self.shape_data, name=name, year=year,
        )
        return self.get_map_plot(shape_data, key, key)

    @staticmethod
    @lru_cache(2048)
    def get_shape_data() -> gpd.geodataframe.GeoDataFrame:
        """Loads the shape data of the map"""
        shape_data = gpd.read_file(SHAPEFILE)[["ADMIN", "ADM0_A3", "geometry"]]
        shape_data.columns = ["country", "country_code", "geometry"]
        shape_data = shape_data.drop(shape_data.index[159])
        return shape_data

    @staticmethod
    @lru_cache(2048)
    def get_owid_data_sets() -> pd.DataFrame:
        """The list of Owid data sets

        Returns:
            pd.DataFrame: A DataFrame with columns=["name", "url"] and index=["name"]
        """
        return pd.read_csv(OWIDDATASETS_FILE).set_index("name")

    @staticmethod
    @lru_cache(2048)
    def get_owid_df(url) -> pd.DataFrame:
        return pd.read_csv(url)

    @classmethod
    def get_owid_data(
        cls,
        owid_data_sets: pd.DataFrame,
        shape_data: gpd.geodataframe.GeoDataFrame,
        name: str,
        year: Optional[int] = None,
        key: Optional[str] = None,
    ) -> gpd.geodataframe.GeoDataFrame:
        """An Owid Data Set combined with the shape_data

        Args:
            owid_data_sets (pd.DataFrame): The list of Owid Data Sets
            shape_data (gpd.geodataframe.GeoDataFrame): The shape data for the map
            name (str): The name of the Owid Data Set to look up.
            year (Optional[int], optional): A year to filter to. Defaults to None.
            key (Optional[str], optional): The name of column containing the values.
            Defaults to None.

        Returns:
            gpd.geodataframe.GeoDataFrame: The Owid Data Sets merged with the shape data
        """
        url = owid_data_sets.loc[name].url
        owid_data = cls.get_owid_df(url)
        if year is not None:
            owid_data = owid_data[owid_data["Year"] == year]
        merged = shape_data.merge(owid_data, left_on="country", right_on="Entity", how="left")

        if key is None:
            key = owid_data.columns[2]
        merged[key] = merged[key].fillna(0)
        return merged, key

    @staticmethod
    def to_geo_json_data_source(data: gpd.geodataframe.GeoDataFrame) -> GeoJSONDataSource:
        """Convert the data to a GeoJSONDataSource

        Args:
            data (gpd.geodataframe.GeoDataFrame): The data

        Returns:
            GeoJSONDataSource: The resulting GeoJson Data
        """
        json_data = json.dumps(json.loads(data.to_json()))
        return GeoJSONDataSource(geojson=json_data)

    @classmethod
    def get_map_plot(
        cls,
        shape_data: gpd.geodataframe.GeoDataFrame,
        value_column: Optional[str] = None,
        title: str = "",
    ):
        """Plot GeoDataFrame as a map


        """
        geosource = cls.to_geo_json_data_source(shape_data)
        palette = brewer["OrRd"][8]
        palette = palette[::-1]
        vals = shape_data[value_column]
        color_mapper = LinearColorMapper(palette=palette, low=vals.min(), high=vals.max())
        color_bar = ColorBar(
            color_mapper=color_mapper,
            label_standoff=8,
            height=20,
            location=(0, 0),
            orientation="horizontal",
        )

        plot = figure(title=title, plot_height=500, tools="", sizing_mode="stretch_width",)
        plot.xgrid.grid_line_color = None
        plot.ygrid.grid_line_color = None
        plot.patches(
            "xs",
            "ys",
            source=geosource,
            fill_alpha=1,
            line_width=0.5,
            line_color="black",
            fill_color={"field": value_column, "transform": color_mapper},
        )
        plot.add_layout(color_bar, "below")
        plot.toolbar.logo = None
        return plot

    def view(self):
        """Map dashboard"""
        css = """
.bk.owid-card {
    border: 1px solid rgba(0,0,0,.125);
    border-radius: 0.25rem;
    font-family: Lato,"Helvetica Neue",Arial,sans-serif;
    font-weight: 400;
    box-shadow: 5px 5px 20px grey;
}
        """
        style = f"<style>{css}</style>"
        content = pn.Column(
            self.param.dataset_name,
            self.map_plot,
            self.param.year,
            pn.Row(pn.layout.HSpacer(), self.download_link, sizing_mode="stretch_width"),
            css_classes=["owid-content"],
            margin=(10, 12, 12, 10),
            sizing_mode="stretch_width",
        )
        card = pn.Column(
            content, css_classes=["owid-card"], sizing_mode="stretch_width", max_width=1000
        )
        app = pn.Column(
            pn.pane.Markdown(__doc__), pn.pane.HTML(style), card, sizing_mode="stretch_width"
        )
        return app


def view():
    """A View of the OwidDashboard. Is here so that the OwidDashboard can be included in the
    Gallery"""
    return OwidDashboard().view()


if __name__.startswith("bk"):
    view().servable()
