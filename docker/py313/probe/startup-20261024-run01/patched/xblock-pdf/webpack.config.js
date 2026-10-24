const path = require('path');

module.exports = {
  entry: './pdf/static/js/pdf_viewer.js',
  output: {
    filename: './pdf/static/js/pdf_view.js',
    path: path.resolve(__dirname),
  }
};
