import React, { Component } from 'react';
var Bootstrap = require('react-bootstrap');
import {connect} from 'react-redux';
var Network = require('../network');
var widgets = require('./main_components');
import { getSpinner } from './util';

class Panel extends Component {
    constructor (props) {
        super(props);
        this.state = {
            template: {
                "title": "",
                "help_url": "",
                "tbl_source": {},
                "content": []
            }, loading: true
        };
        this.getPanel = this.getPanel.bind(this);
    }

    getPanel (id, server, args) {
        var me = this;
        var data = {'panel': id, 'server_name': server};
        if(args !== ""){
            data['args'] = args.indexOf(',') > -1 ? args.split(",") : args;
            this.props.dispatch({type: 'CHANGE_PANEL', panel: id, server: server, args: data['args']});
        }else{
            this.props.dispatch({type: 'CHANGE_PANEL', panel: id, server: server});
        }
        Network.post('/api/panels/get_panel', this.props.auth.token, data).done(function (data) {
            if(typeof data.tbl_source !== 'undefined'){
                me.props.dispatch({type: 'ADD_DATA', tables: data.tbl_source});
            }
            if(typeof data.form_source !== 'undefined'){
                me.props.dispatch({type: 'ADD_DROPDOWN', dropdowns: data.form_source});
            }
            me.setState({template: data, loading: false});
        }).fail(function (msg) {
            me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        });
    }

    componentDidMount () {
        var args = "args" in this.props.params && this.props.params.args ? this.props.params.args : "";
        this.getPanel(this.props.params.id, this.props.params.server, args);
    }

    componentWillReceiveProps (nextProps) {
        if (nextProps.params.id !== this.props.params.id || nextProps.params.server !== this.props.params.server) {
            this.setState({loading: true});
            //this.props.dispatch({type: 'RESET_FILTER'});
            var args = "args" in nextProps.params && nextProps.params.args ? nextProps.params.args : "";
            this.getPanel(nextProps.params.id, nextProps.params.server, args);
        }
    }

    componentWillUnmount () {
        this.props.dispatch({type: 'RESET_FILTER'});
    }

    render () {
        var redux = {};
        var ModalRedux = connect(function(state){
            return {auth: state.auth, modal: state.modal, panel: state.panel, alert: state.alert};
        })(widgets.Modal);

        var elements = this.state.template.content.map(function(element) {
            element.key = element.name;
            if(Object.keys(redux).indexOf(element.type) < 0){
                var Component = widgets[element.type];
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
            }
            var Redux = redux[element.type];
            return React.createElement(Redux, element);
        });
        var loading = this.state.loading;
        const blockStyle = {
            visibility: loading ? "hidden": "visible"
        };
        return (
            <div>
                {loading && getSpinner()}
                <div key={this.props.params.id} style={blockStyle}>
                    <Bootstrap.PageHeader>{this.state.template.title} <small>{this.props.params.server}</small></Bootstrap.PageHeader>
                    {elements}
                    <ModalRedux />
                </div>
            </div>
        );
    }

}

module.exports = connect(function(state){
    return {auth: state.auth, panel: state.panel, alert: state.alert, table: state.table, filter: state.filter};
})(Panel);

