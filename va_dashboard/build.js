var fs = require("fs");
var browserify = require('browserify');
var resolve = require('path').resolve;

const args = require('minimist')(process.argv);
var mode = args['mode'];
console.log('Arguments', args);
console.log('Mode', mode);

var bundle_obj = browserify(resolve(__dirname, "app.js"))
	.transform(resolve(__dirname, "node_modules/babelify"), {presets: ["react", "es2015"]});
if (mode != 'development'){
    bundle_obj = bundle_obj.transform('uglifyify', { global: true });
}

bundle_obj = bundle_obj.bundle();

if (mode!= 'development'){
	bundle_obj = bundle_obj.pipe(require('minify-stream')({sourceMap: false}));
}

bundle_obj = bundle_obj.pipe(fs.createWriteStream(resolve(__dirname, "static/bundle.js")));
