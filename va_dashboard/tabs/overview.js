import React, { Component } from 'react';
import {connect} from 'react-redux';
import {Chart, Doughnut, Bar, defaults} from "react-chartjs-2";
var vis = require('../static/vis');
var Network = require('../network');
import {getRandomColors, getSpinner, getTimestamp} from './util';
import {hashHistory} from 'react-router';

const LOGS = [
  { color: 'rgb(150, 230, 118)', iconColor: '#dff0d8', key: 'info_logs', icon: 'fa fa-info-circle', value: 135, title: 'Total Info Logs', type: 'info'},
  { color: 'rgb(249, 196, 98)', iconColor: '#ffedcc', key: 'warning_logs', icon: 'fa fa-exclamation-circle', value: 20, title: 'Total Warning Logs', type: 'warning'},
  { color: 'rgb(242, 140, 140)', iconColor: '#f2dede', key: 'critical_logs', icon: 'fa fa-times-circle ', value: 12, title: 'Total Critical Logs', type: 'critical'}
];
const SERVICES = [
  { color: 'rgb(150, 230, 118)', iconColor: '#dff0d8', key: 'passing_services', icon: 'fa fa-info-circle', value: 135, title: 'Total Passing Services'},
  { color: 'rgb(249, 196, 98)', iconColor: '#ffedcc', key: 'warning_services', icon: 'fa fa-exclamation-circle', value: 30, title: 'Total Warning Services'},
  { color: 'rgb(242, 140, 140)', iconColor: '#f2dede', key: 'critical_services', icon: 'fa fa-times-circle ', value: 23, title: 'Total Critical Services'}
]
// const SERVICES = [
//   { color: '#dff0d8', iconColor: 'rgb(150, 230, 118)', icon: 'fa fa-info-circle', value: 135, title: 'Total Passing Services'},
//   { color: '#ffedcc', iconColor: 'rgb(249, 196, 98)', icon: 'fa fa-exclamation-circle', value: 30, title: 'Total Warning Services'},
//   { color: '#f2dede', iconColor: 'rgb(242, 140, 140)', icon: 'fa fa-times-circle ', value: 23, title: 'Total Critical Services'}
// ]

Chart.defaults.global.defaultFontFamily = 'Ubuntu';
Chart.pluginService.register({
    beforeDraw: function(chart) {
        if(chart.config.type === "doughnut"){
            let width = chart.chart.width,
                height = chart.chart.height,
                ctx = chart.chart.ctx,
                text, textX, textY;

            ctx.restore();
            var fontSize = (height / 114).toFixed(2);

            var allData = chart.data.datasets[0].data;
            if(chart.config.options.rotation == Math.PI){
                let total = 0;
                for (var i in allData) {
                    if(!isNaN(allData[i]))
                        total += allData[i];
                }
                if(isNaN(allData[allData.length-1])){
                    let unit = "";
                    if(chart.titleBlock.options.text == "MEMORY"){
                        unit = " GB";
                    }else if(chart.titleBlock.options.text == "STORAGE"){
                        unit = " GB";
                    }
                    text = total.toString() + unit;
                }else{
                    var percentage = Math.round(((total - allData[allData.length-1]) / total) * 100);
                    text = percentage.toString() + "%";
                }

                textX = Math.round((width - ctx.measureText(text).width) / 2);
                textY = height / 1.2;
            }else{
                fontSize = (height / 114).toFixed(2);
                if(!allData[0])
                    allData[0] = 0
                if(chart.titleBlock.options.text == "MEMORY"){
                    text = chart.config.options.customInnerData + " GB";
                }else if(chart.titleBlock.options.text == "USERS"){
                    text = allData[0] + "+" + allData[1];
                }else{
                    text = chart.config.options.customInnerData;
                }

                textX = Math.round((width - ctx.measureText(text).width) / 2);
                textY = height / 1.5;
            }
            ctx.font = fontSize + "em sans-serif";
            ctx.textBaseline = "middle";

            ctx.fillText(text, textX, textY);
            ctx.save();
        }
    }
});

class Overview extends Component {
    constructor (props) {
        super(props)
        defaults.global.legend.display = false;
        this.state = {
          providers: {},
          loading: true,
          stats: {
            critical_logs: 0,
            critical_services: 0,
            info_logs: 0,
            passing_services: 0,
            warning_logs: 0,
            warning_services: 0
          },
        };
        this.getProviders = this.getProviders.bind(this);
    }
    componentDidMount() {
        this.getProviders();
    }
    getProviders(){
        var data = {providers: [], sort_by_location: true};
        var me = this;
        // Network.post('/api/providers/info', this.props.auth.token, data).done(function(data) {
        //     me.setState({providers: data, loading: false});
        // }).fail(function (msg) {
        //     me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        // });
        var n1 = Network.post('/api/providers/info', this.props.auth.token, data).fail(function (msg) {
            me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        });
        var n2 = Network.get('/api/panels/get_services_and_logs', this.props.auth.token, {}).fail(function (msg) {
            me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        });
        $.when( n1, n2 ).done(function ( resp1, resp2 ) {
          console.log("get_services_and_logs", resp2);
          me.setState({providers: resp1, loading: false, stats: resp2});
        });
    }
    render() {
        var DiagramRedux = connect(function(state){
            return {auth: state.auth, sidebar: state.sidebar};
        })(Diagram);
        var LogRedux = connect(function(state){
            return {auth: state.auth};
        })(Log);
        var diagram = {}, provider_rows = [];
        for(let loc in this.state.providers) {
            diagram[loc] = [];
        }
        for(let loc in this.state.providers) {
            var provider = this.state.providers[loc];
            for(var key=0; key < provider.length; key++){
                var pp = provider[key], provider_servers = [];
                for(var kkey=0; kkey < pp.servers.length; kkey++) {
                    var ii = pp.servers[kkey];
                    provider_servers.push( {name: ii.hostname.split('.', 1)[0], ip: ii.ip} );
                }
                diagram[loc].push({name: pp.provider_name, servers: provider_servers});
                if(pp.provider_name && pp.provider_usage.used_cpus && pp.provider_usage.used_ram && pp.provider_usage.used_disk)
                    provider_rows.push({name: pp.provider_name, servers: pp.servers, provider_usage: pp.provider_usage});
            }
        }
        var provider_redux = null;
        if(provider_rows.length > 0){
            provider_redux = <ProviderRows providers={provider_rows} />;
        }
        return (
            <div>
                <DiagramRedux providers={diagram} />
                <div className="graph-block">
                    {this.state.loading && getSpinner({top: '30%'})}
                    {provider_redux}
                </div>
                <LogRedux {... this.state.stats} />
            </div>);
    }
}

class Diagram extends Component{
    constructor(props){
        super(props);
        this.state={};
    }
    componentDidMount(){
        console.log(this.props);
        const graphOptions = {
            layout: {
                hierarchical: {
                    direction: "UD",
                    sortMethod: "directed",
                    nodeSpacing: 120,
                    levelSeparation: 50
                }
            },
            edges: {
                color: "#000000",
                arrows: {
                    to: {
                        enabled: false,
                        scaleFactor: 0.5
                    }
                }
            },
            nodes: {
                size: 15,
                font: {
                    size : 11,
                    color : 'white',
                    face : 'Ubuntu'
                },
                margin: {
                    top: 8,
                    right: 8,
                    left: 8,
                    bottom: 8
                }
            },
            physics: {
                enabled: false
            }
        };

        var container = document.getElementById('mynetwork');

        var graph = {nodes: [], edges: []}, ll = 0;
        graph.nodes.push({id: 'master', label: "va-master", shape: 'box', color: '#337ab7'});
        for(var location in this.props.providers){
            var provider = this.props.providers[location];
            var txt = location;
            txt = txt.length > 17 ? txt.substring(0,17) : txt;
            graph.nodes.push({id: location, label: txt, shape: 'box', color: '#97c2fc'});
            graph.edges.push({from: 'master', to: location});
            ll++;

            for(let i=0; i<provider.length; i++){
                let p = provider[i];
                txt = p.name;
                let id = location + "/" + txt;
                if(txt){
                    txt = txt.length > 17 ? txt.substring(0,17) : txt;
                    graph.nodes.push({id: id, label: txt, shape: 'box', color: {border: '#696969', background: 'gray', highlight: {border: 'gray', background: '#909090'}}});
                    graph.edges.push({from: location, to: id});
                }else{
                    id = location;
                }

                for(let j=0; j<p.servers.length; j++){
                    let server = p.servers[j], newId = id + "/" + server.name;
                    txt = server.name + "\nIP: " + server.ip;
                    graph.nodes.push({id: newId, label: txt, shape: 'box', color: '#4bae4f'});
                    graph.edges.push({from: id, to: newId});
                }
            }
        }
        console.log('graph_data', graph);
        var data = {
                nodes: new vis.DataSet(graph.nodes),
                edges: new vis.DataSet(graph.edges)
        };

        var network = new vis.Network(this.refs.mynetwork, data, graphOptions);
    }

    render(){
        var style = { width: '100%', height: '180px' };
        return (
            <div className="card panel-default custom-panel" style={{marginBottom: '0px'}}>
                <div className="panel-heading">Diagram</div>
                <div className="panel-body">
                    <div ref="mynetwork" style={style} events={{}}></div>
                    {/*<div id="mynetwork" style={style} events={{}}></div>*/}
                    <div className="hidden">{this.props.sidebar.collapsed}</div>
                </div>
            </div>
        );
    }
}

const Provider = (props) => {
    var cpuData = [], ramData = [], diskData = [], cost = 0, e_cost = 0;
    var labels = props.chartData.map((server) => {
        cpuData.push(server.used_cpu);
        ramData.push(server.used_ram);
        diskData.push(server.used_disk);
        cost += server.cost;
        e_cost += server.estimated_cost;
        return server.hostname;
    });
    labels.push("Free");
    var usage = props.provider_usage;
    cpuData.push(usage.free_cpus);
    ramData.push(usage.free_ram);
    diskData.push(usage.free_disk);
    var chartData = [cpuData, ramData, diskData];
    var colors = getRandomColors(labels.length+1);

    var DoughnutRedux = connect(function(state){
        return {auth: state.auth};
    })(DoughnutComponent);
    if(!isNaN(cost)){
        cost = Math.round(cost);
    }
    if(!isNaN(e_cost)){
        e_cost = Math.round(e_cost);
    }
    return (
        <div id="billing-panel-content">
            <DoughnutRedux data={chartData[0]} labels={labels} colors={colors} title="CPU" />
            <DoughnutRedux data={chartData[1]} labels={labels} colors={colors} title="MEMORY" />
            <DoughnutRedux data={chartData[2]} labels={labels} colors={colors} title="STORAGE" />
            <div className="billing-info" style={{visibility: 'hidden'}}>
                <div>
                    <div className="provider-billing">{cost}</div>
                    <div>Current monthly cost</div>
                </div>
                <div>
                    <div className="provider-billing">{e_cost}</div>
                    <div>Monthly estimated cost</div>
                </div>
            </div>
        </div>
    );
}

class ProviderRows extends Component {
    constructor (props) {
        super(props);
        this.state = {index: 0};
        this.nextProvider = this.nextProvider.bind(this);
        this.prevProvider = this.prevProvider.bind(this);
    }
    nextProvider() {
        if(this.state.index < this.props.providers.length-1)
            this.setState({index: this.state.index + 1});
    }
    prevProvider() {
        if(this.state.index > 0)
            this.setState({index: this.state.index - 1});
    }
    render() {
        let provider = this.props.providers[this.state.index];
        let class1 = this.state.index <= 0 ? 'disabled' : 'not-disabled';
        let class2 = this.state.index >= this.props.providers.length - 1 ? 'disabled' : 'not-disabled';
        return (
            <div className="provider-billing-block card panel-default custom-panel" style={{marginBottom: '0px'}}>
                <div className="panel-heading">{provider.name + " / Instances: " + provider.servers.length}</div>
                <div className="panel-body">
                    <span className={'glyphicon glyphicon-arrow-left ' + class1} onClick={this.prevProvider}></span>
                    <Provider key={provider.name} title={provider.name} chartData={provider.servers} provider_usage={provider.provider_usage} />
                    <span className={'glyphicon glyphicon-arrow-right ' + class2} onClick={this.nextProvider}></span>
                </div>
            </div>
        );
    }
}

const DoughnutComponent = (props) => {
    const chartOptions = {
            maintainAspectRatio: false,
            title: {
                display: true,
                text: props.title
            },
            cutoutPercentage: 70,
            rotation: 1 * Math.PI,
            circumference: 1 * Math.PI
        }, chartData = {
            labels: props.labels,
            datasets: [
                {
                    data: props.data,
                    backgroundColor: props.colors,
                    hoverBackgroundColor: props.colors
                }
            ]
        };
    return (
        <div className="chart">
            <Doughnut data={chartData} options={chartOptions}/>
        </div>
    );
}

const styles = {
  tile: {
    flex: 1,
    padding: '10px 5px',
    margin: '0 10px',
    textAlign: 'center',
    cursor: 'pointer',
    // color: '#fff'
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    backgroundColor: '#fff',
    borderLeftWidth: 3,
    borderLeftStyle: 'solid'
  },
  icon: {
    fontSize: '18px',
    marginBottom: '5px'
  },
  value: {
    marginTop: '5px',
    fontSize: '20px',
    fontWeight: 700,
    lineHeight: 1.2
  }
}

const Log = (props) => {
    return (
        <div className="stats-block">
          <div>
          {
            LOGS.map(l => (
              <div onClick={ () => hashHistory.push('/log/' + l.type) } key={l.title} className="tile" style={{borderLeftColor: l.color}}>
                <i className={l.icon + ' tile-icon'} style={{color: l.color}} />
                <div style={styles.value}>{props[l.key]}</div>
                <small>{l.title}</small>
              </div>
            ))
          }
          </div>
          <div style={{marginTop: 20}}>
          {
            SERVICES.map(l => (
              <div key={l.title} className="tile" style={{borderLeftColor: l.color}}>
                <i className={l.icon + ' tile-icon'} style={{color: l.color}} />
                <div style={styles.value}>{props[l.key]}</div>
                <small>{l.title}</small>
              </div>
            ))
          }
          </div>
        </div>
    );
}

module.exports = connect(function(state) {
    return {auth: state.auth};
})(Overview);
