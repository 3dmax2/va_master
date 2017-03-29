var React = require('react');
var Bootstrap = require('react-bootstrap');
var connect = require('react-redux').connect;
var Network = require('../network');
var ReactDOM = require('react-dom');
var components = require('./basic_components');
var Reactable = require('reactable');
var Router = require('react-router');
var LineChart = require("react-chartjs-2").Line;
var defaults = require("react-chartjs-2").defaults;

var Div = React.createClass({

    render: function () {
        var redux = {};
        var elements = this.props.elements.map(function(element) {
            element.key = element.name;
            var Component = components[element.type];
            redux[element.type] = connect(function(state){
                var newstate = {auth: state.auth};
                if(typeof element.reducers !== 'undefined'){
                    var r = element.reducers;
                    for (var i = 0; i < r.length; i++) {
                        newstate[r[i]] = state[r[i]];
                    }
                }
                return newstate;
            })(Component);
            var Redux = redux[element.type];
            return React.createElement(Redux, element);
        });
        var classes = this.props.class;
        if(typeof this.props.div !== 'undefined'){
            //TODO add other classes
            classes = this.props.div.show;
        }
        return (
            <div className={classes}>
                {elements}
            </div>
        );
    }
});

var MultiTable = React.createClass({

    render: function () {
        var redux = {}, tables = [];
        for(x in this.props.table){
            var elements = this.props.elements.map(function(element) {
                element.name = x;
                element.key = element.type + element.name;
                var Component = components[element.type];
                redux[element.type] = connect(function(state){
                    var newstate = {auth: state.auth};
                    if(typeof element.reducers !== 'undefined'){
                        var r = element.reducers;
                        for (var i = 0; i < r.length; i++) {
                            newstate[r[i]] = state[r[i]];
                        }
                    }
                    return newstate;
                })(Component);
                var Redux = redux[element.type];
                return React.createElement(Redux, element);
            }.bind(this));
            tables.push(elements);
        }
        return (
            <div className="multi">
                {tables}
            </div>
        );
    }
});

var Chart = React.createClass({
    getInitialState: function () {
        defaults.global.legend.display = true;
        defaults.global.legend.position = 'right';
        var chartData = this.getData(this.props.data, false);
        return {chartOptions: {
                    maintainAspectRatio: false,
                    responsive: true,
                    scales: {
                        xAxes: [{
                            type: 'time',
                            stacked: true,
                            time: {
                                displayFormats: {
                                    minute: 'HH:mm',
                                    hour: 'HH:mm',
                                    second: 'HH:mm:ss',
                                },
                                tooltipFormat: 'DD/MM/YYYY HH:mm',
                                unit: 'minute',
                                unitStepSize: 5
                            }
                        }],
                        yAxes: [{
                            stacked: true
                        }]
                    }
                }, chartData: chartData};
    },
    getData: function(data, check) {
        var datasets = [], times = [], chartData = {}, prevColors = {};
        if(check){
            for(var i=0; i < this.state.chartData.datasets.length; i++) {
                dataset = this.state.chartData.datasets[i];
                prevColors[dataset.label] = dataset.backgroundColor;
            }
        }
        for(var key in data){
            var obj = {}, prevColor = prevColors[key];
            var color = prevColor || this.getRandomColor();
            obj.label = key;
            obj.data = [];
            var chart_data = data[key];
            for(var i=0; i<chart_data.length; i++){
                obj.data.push(chart_data[i].y);
            }
            obj.backgroundColor = color;
            obj.borderColor = color;
            datasets.push(obj);
        }
        for(var i=0; i<data[key].length; i++){
            times.push(data[key][i].x * 1000);
        }
        chartData.labels = times;
        chartData.datasets = datasets;
        return chartData;
    },
    getRandomColor: function() {
        var letters = '0123456789ABCDEF'.split('');
        var color = '#';
        for (var i = 0; i < 6; i++ ) {
            color += letters[Math.floor(Math.random() * 16)];
        }
        return color;
    },
    btn_click: function(period, interval, unit, step) {
        var instance_name = this.props.panel.instance;
        var data = {"instance_name": instance_name, "args": [this.props.host, this.props.service, period, interval]};
        var me = this;
        Network.post('/api/panels/chart_data', this.props.auth.token, data).done(function(d) {
            var chartOptions = Object.assign({}, me.state.chartOptions);
            chartOptions.scales.xAxes[0].time.unit = unit;
            chartOptions.scales.xAxes[0].time.unitStepSize = step;
            me.setState({chartData: me.getData(d[instance_name], true), chartOptions: chartOptions});
        }).fail(function (msg) {
            me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        });
    },
    render: function () {
        return (
            <div>
                <div className="panel_chart">
                    <LineChart name="chart" height={200} data={this.state.chartData} options={this.state.chartOptions} redraw />
                </div>
                <div id="chartBtns">
                  <button className='btn btn-primary bt-sm chartBtn' onClick = {this.btn_click.bind(this, "-1h", "300", 'minute', 5)}>Last hour</button>
                  <button className='btn btn-primary bt-sm chartBtn' onClick = {this.btn_click.bind(this, "-5h", "1500", 'hour', 1)}>Last 5 hours</button>
                  <button className='btn btn-primary bt-sm chartBtn' onClick = {this.btn_click.bind(this, "-1d", "7200", 'hour', 4)}>Last day</button>
                  <button className='btn btn-primary bt-sm chartBtn' onClick = {this.btn_click.bind(this, "-7d", "86400", 'day', 1)}>Last week</button>
                  <button className='btn btn-primary bt-sm chartBtn' onClick = {this.btn_click.bind(this, "-1m", "86400", 'day', 5)}>Last month</button>
                </div>
            </div> 
        );
    }
});

var Table = React.createClass({
    btn_clicked: function(id, evtKey){
        if(evtKey == 'chart'){
            var newName = this.props.name.replace(/\s/g, "_");
            var newId = id.replace(/:/g, "_");
            var newId = newId.replace(/\s/g, "_");
            Router.hashHistory.push('/chart_panel/' + this.props.panel.instance + '/' + newName + '/' + newId);
        }else if('modals' in this.props && evtKey in this.props.modals){
            if("readonly" in this.props){
                var rows = this.props.table[this.props.name].filter(function(row) {
                    if(row[this.props.id] == id){
                        return true;
                    }
                    return false;
                }.bind(this));
                var readonly = {};
                for(key in this.props.readonly){
                    readonly[this.props.readonly[key]] = rows[0][key];
                }
                this.props.dispatch({type: 'SET_READONLY', readonly: readonly});
            }
            var modal = Object.assign({}, this.props.modals[evtKey]);
            modal.args = [id];
            modal.table_name = this.props.name;
            modal.refresh_action = this.props.source;
            this.props.dispatch({type: 'OPEN_MODAL', template: modal});
        }else if("panels" in this.props && evtKey in this.props.panels){
            Router.hashHistory.push('/subpanel/' + this.props.panels[evtKey] + '/' + this.props.panel.instance + '/' + id);
        }else{
            var data = {"instance_name": this.props.panel.instance, "action": evtKey, "args": [id]};
            var me = this;
            Network.post('/api/panels/action', this.props.auth.token, data).done(function(d) {
                var msg = d[me.props.panel.instance];
                if(msg){
                    me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
                }else{
                    data.action = me.props.source;
                    data.args = [];
                    Network.post('/api/panels/action', me.props.auth.token, data).done(function(d) {
                        var msg = d[data.instance_name];
                        if(msg){
                            me.props.dispatch({type: 'CHANGE_DATA', data: msg, name: me.props.name});
                        }
                    });
                }
            }).fail(function (msg) {
                me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
            });
        }
    },
    render: function () {
        var pagination = "pagination" in this.props ? this.props.pagination : true;
        if(typeof this.props.table[this.props.name] === 'undefined')
            return null;
        var cols = [], tbl_cols = this.props.columns.slice(0), tbl_id = this.props.id;
        for(var i=0; i<tbl_cols.length; i++){
            if(tbl_cols[i].key === ""){
                tbl_cols[i] = {key: this.props.name, label: this.props.name};
            }
            cols.push(tbl_cols[i].key);
        }
        if(!tbl_id){
            tbl_id = this.props.name;
        }
        var action_col = false, action_length = 0;
        if(this.props.hasOwnProperty('actions')){
            var action_col = true, action_length = this.props.actions.length;
            if(action_length > 1){
                var actions = this.props.actions.map(function(action) {
                    var className = "";
                    if(typeof action.class !== 'undefined'){
                        className = action.class;
                    }
                    return (
                        <Bootstrap.MenuItem key={action.name} eventKey={action.action} className={className}>{action.name}</Bootstrap.MenuItem>
                    );
                });
            }
        }
        var rows = this.props.table[this.props.name].map(function(row) {
            var columns = cols.map(function(col) {
                return (
                    <Reactable.Td key={col} column={col}>
                        {row[col]}
                    </Reactable.Td>
                );
            });
            var key = row[tbl_id];
            if(action_col){
                action_col = (
                    <Reactable.Td column="action">
                        {action_length > 1 ? (
                            <Bootstrap.DropdownButton bsStyle='primary' title="Choose" onSelect = {this.btn_clicked.bind(this, key)}>
                                {actions}
                            </Bootstrap.DropdownButton>
                        ) : (
                            <Bootstrap.Button bsStyle='primary' onClick={this.btn_clicked.bind(this, key, this.props.actions[0].action)}>
                                {this.props.actions[0].name}
                            </Bootstrap.Button>
                        )}
                    </Reactable.Td>
                );
            }
            var rowClass = "";
            if(typeof this.props.rowStyleCol !== 'undefined'){
                rowClass = "row-" + this.props.rowStyleCol + "-" + row[this.props.rowStyleCol];
            }
            return (
                <Reactable.Tr className={rowClass} key={key}>
                    {columns}
                    {action_col}
                </Reactable.Tr>
            )
        }.bind(this));
        var filterBy = "";
        if('filter' in this.props){
            filterBy = this.props.filter.filterBy;
        }
        return (
            <div>
            { pagination ? ( <Reactable.Table className="table striped" columns={tbl_cols} itemsPerPage={10} pageButtonLimit={10} noDataText="No matching records found." sortable={true} filterable={cols} filterBy={filterBy} hideFilterInput >
                {rows}
            </Reactable.Table> ) :
            ( <Reactable.Table className="table striped" columns={tbl_cols} noDataText="No matching records found." sortable={true} hideFilterInput >
                {rows}
            </Reactable.Table> )}
            </div>
        );
    }
});

var Modal = React.createClass({

    getInitialState: function () {
        var content = this.props.modal.template.content, data = [];
        for(j=0; j<content.length; j++){
            if(content[j].type == "Form"){
                var elem = content[j].elements;
                for(i=0; i<elem.length; i++){
                    data[i] = elem[i].value;
                }
            }
        }
        var args = [];
        if("args" in this.props.modal.template){
            args = this.props.modal.template.args;
        }
        return {
            data: data,
            focus: "",
            args: args
        };
    },

    close: function() {
        this.props.dispatch({type: 'CLOSE_MODAL'});
    },

    action: function(action_name) {
        var data = {"instance_name": this.props.panel.instance, "action": action_name, "args": this.state.args.concat(this.state.data)};
        var me = this;
        Network.post("/api/panels/action", this.props.auth.token, data).done(function(d) {
            var msg = d[me.props.panel.instance];
            if(msg){
                me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
                me.props.dispatch({type: 'CLOSE_MODAL'});
            }else{
                me.props.dispatch({type: 'CLOSE_MODAL'});
                if('refresh_action' in me.props.modal.template){
                    var data = {"instance_name": me.props.panel.instance, "action": me.props.modal.template.refresh_action, "args": []};
                    Network.post('/api/panels/action', me.props.auth.token, data).done(function(d) {
                        var msg = d[data.instance_name];
                        if(msg){
                            me.props.dispatch({type: 'CHANGE_DATA', data: msg, name: me.props.modal.template.table_name});
                        }
                    });
                }
            }
        }).fail(function (msg) {
            me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        });
    },

    form_changed: function(e) {
        var name = e.target.name;
        var val = e.target.value;
        var id = e.target.id;
        var data = this.state.data;
        if(e.target.type == "checkbox"){
            val = e.target.checked;
        }else{
            this.setState({focus: name});
        }
        data[id] = val;
        this.setState({data: data});
    },

    render: function () {
        var btns = this.props.modal.template.buttons.map(function(btn){
            if(btn.action == "cancel"){
                action = this.close;
            }else{
                action = this.action.bind(this, btn.action);
            }
            return <Bootstrap.Button key={btn.name} onClick={action} bsStyle = {btn.class}>{btn.name}</Bootstrap.Button>;
        }.bind(this));

        var redux = {};
        var elements = this.props.modal.template.content.map(function(element) {
            element.key = element.name;
            var Component = components[element.type];
            if(element.type == "Form"){
                element.data = this.state.data;
                element.form_changed = this.form_changed;
                element.focus = this.state.focus;
            }
            redux[element.type] = connect(function(state){
                var newstate = {auth: state.auth};
                if(typeof element.reducers !== 'undefined'){
                    var r = element.reducers;
                    for (var i = 0; i < r.length; i++) {
                        newstate[r[i]] = state[r[i]];
                    }
                }
                return newstate;
            })(Component);
            var Redux = redux[element.type];
            return React.createElement(Redux, element);
        }.bind(this));
        return (
            <Bootstrap.Modal show={this.props.modal.isOpen} onHide={this.close}>
            <Bootstrap.Modal.Header closeButton>
              <Bootstrap.Modal.Title>{this.props.modal.template.title}</Bootstrap.Modal.Title>
            </Bootstrap.Modal.Header>

            <Bootstrap.Modal.Body>
                {elements}
            </Bootstrap.Modal.Body>

            <Bootstrap.Modal.Footer>
              {btns}
            </Bootstrap.Modal.Footer>

        </Bootstrap.Modal>
        );
    }
});

var Form = React.createClass({

    render: function () {
        var redux = {};

        var inputs = this.props.elements.map(function(element, index) {
            var type = element.type;
            if(type.charAt(0) === type.charAt(0).toLowerCase()){
                if(type == "checkbox"){
                    return ( <Bootstrap.Checkbox id={index} key={element.name} name={element.name} checked={this.props.data[index]} inline onChange={this.props.form_changed}>{element.label}</Bootstrap.Checkbox>);
                }
                if(type == "label"){
                    return ( <label id={index} key={element.name} name={element.name} className="block">{element.name}</label>);
                }
                if(type == "multi_checkbox"){
                    return ( <Bootstrap.Checkbox id={index} key={element.name} name={element.name} checked={this.props.data[index]} onChange={this.props.form_changed}>{element.label}</Bootstrap.Checkbox>);
                }
                if(type == "readonly_text"){
                    return ( <Bootstrap.FormControl id={index} key={element.name} type={type} name={element.name} value={this.props.form.readonly[element.name]} disabled /> );
                }
                if(type == "dropdown"){
                    return ( <Bootstrap.FormControl id={index} key={element.name} name={element.name} componentClass="select" placeholder={element.value[0]}>
                        {element.value.map(function(option, i) {
                            return <option key={i} value={option}>{option}</option>
                        })}
                    </Bootstrap.FormControl> );
                }
                return ( <Bootstrap.FormControl id={index} key={element.name} type={type} name={element.name} value={this.props.data[index]} placeholder={element.label} onChange={this.props.form_changed} autoFocus={element.name == this.props.focus} /> );
            }
            element.key = element.name;
            if(Object.keys(redux).indexOf(type) < 0){
                if(type == "Button" && element.action == "modal"){
                    var modalTemplate = Object.assign({}, element.modal), args = [];
                    if('args' in this.props){
                        for(var key in this.props.args){
                            val = this.props.args[key]
                            if(!val){
                                val = this.props.name;
                            }
                            args.push(val);
                        }
                    }
                    modalTemplate.args = args;
                    element.modalTemplate = modalTemplate;
                }
                var Component = components[type];
                redux[type] = connect(function(state){
                    var newstate = {auth: state.auth};
                    if(typeof element.reducers !== 'undefined'){
                        var r = element.reducers;
                        for (var i = 0; i < r.length; i++) {
                            newstate[r[i]] = state[r[i]];
                        }
                    }
                    return newstate;
                })(Component);
            }
            var Redux = redux[type];
            return React.createElement(Redux, element);
        }.bind(this));

        return (
            <form className={this.props.class}>
                {inputs}
            </form>
        );
    }
});

components.Div = Div;
components.MultiTable = MultiTable;
components.Chart = Chart;
components.Table = Table;
components.Form = Form;
components.Modal = Modal;

module.exports = components;
