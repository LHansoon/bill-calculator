const container = document.querySelector('#example');
let previous_loc = null;

var data = [
    ['', 'Tesla', 'Volvo', 'Toyota', 'Ford'],
    ['2019', 10, 11, 12, 13],
    ['2020', 20, 11, 14, 13],
    ['2021', 30, 15, 12, 13]
  ];

const hot = new Handsontable(container, {
  data: data,
  rowHeaders: true,
  colHeaders: true,
  height: 'auto',
  autoWrapRow: true,
  autoWrapCol: true,
  licenseKey: 'non-commercial-and-evaluation', // for non-commercial use only
  afterSelection: (row, column, row2, column2, preventScrolling, selectionLayerLevel) => {
    // If set to `false` (default): when cell selection is outside the viewport,
    // Handsontable scrolls the viewport to cell selection's end corner.
    // If set to `true`: when cell selection is outside the viewport,
    // Handsontable doesn't scroll to cell selection's end corner.
    if (previous_loc !== row + " " + column) {
      let selected = hot.getSelected() || [];
      let data = hot.getData(...selected[0]);

      console.log(data[0][0]);

      // if (selected.length === 1) {
      //   data = hot.getData(selected[0]);
      // } else {
      //   for (let i = 0; i < selected.length; i += 1) {
      //     const item = selected[i];
      //
      //     data.push(hot.getData(item));
      //   }
      // }

      // output.innerText = JSON.stringify(data);
      previous_loc = row + " " + column;
    }

  }
});