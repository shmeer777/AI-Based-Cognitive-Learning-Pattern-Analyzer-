let captchaText="";
let chartInstance=null;

function generateCaptcha(){
    const canvas=document.getElementById("captchaCanvas");
    const ctx=canvas.getContext("2d");
    ctx.clearRect(0,0,canvas.width,canvas.height);
    const chars="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    captchaText="";
    for(let i=0;i<5;i++){
        captchaText+=chars.charAt(Math.floor(Math.random()*chars.length));
    }
    ctx.fillStyle="#e3f2fd";
    ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.font="30px Arial";
    ctx.textBaseline="middle";
    for(let i=0;i<captchaText.length;i++){
        const x=30+i*35;
        const y=canvas.height/2;
        ctx.save();
        ctx.translate(x,y);
        ctx.rotate((Math.random()-0.5)*0.5);
        ctx.fillStyle="#0d47a1";
        ctx.fillText(captchaText[i],0,0);
        ctx.restore();
    }
    ctx.beginPath();
    ctx.moveTo(10,Math.random()*canvas.height);
    ctx.lineTo(canvas.width-10,Math.random()*canvas.height);
    ctx.strokeStyle="red";
    ctx.lineWidth=2;
    ctx.stroke();
}

function validateForm(){
    const userCaptcha=document.getElementById("captchaInput").value;
    const username=document.getElementById("username").value;
    if(userCaptcha!==captchaText){
        alert("Incorrect Captcha ❌");
        generateCaptcha();
        return false;
    }
    document.getElementById("loginPage").style.display="none";
    document.getElementById("dashboard").style.display="block";
    document.getElementById("dashboardTitle").innerText=username+" Dashboard";
    document.getElementById("studentName").innerText=username;
    fetchAnalysis();
    fetchHistory(username);
    fetchMarks();
    fetchAllData();
    return false;
}

function generateChart(serverData){
    const ctx=document.getElementById("marksChart").getContext("2d");

    let labels, marks;
    if(Array.isArray(serverData) && serverData.length){
        labels = serverData.map(r=>"ID " + r.student_id);
        marks = serverData.map(r=> Math.round(r.accuracy * 100));
    } else {
        labels=['Maths','Physics','DSA','DBMS','OS'];
        marks=[85,78,92,88,74];
    }

    if(chartInstance) chartInstance.destroy();

    chartInstance=new Chart(ctx,{
        type:'bar',
        data:{
            labels:labels,
            datasets:[{
                label: serverData? 'Accuracy (%)' : 'Marks',
                data:marks,
                backgroundColor:'#1565c0',
                borderColor:'#0d47a1',
                borderWidth:2
            }]
        },
        options:{
            responsive:true,
            maintainAspectRatio:false,
            scales:{
                y:{beginAtZero:true,max:100}
            },
            plugins:{
                title:{display:true,text:'Current Marks/Accuracy'}
            }
        }
    });
}

window.onload=function(){
    generateCaptcha();
};

function fetchAnalysis(){
    fetch('/analyze')
        .then(resp=>resp.json())
        .then(data=>{
            console.log('backend analysis', data);
            generateChart(data);
        })
        .catch(err=>{
            console.error('error fetching analysis', err);
            generateChart();
        });
}

function fetchHistory(studentId){
    fetch(`/history/${studentId}`)
        .then(r=>r.json())
        .then(data=>{
            console.log('history data', data);
            if(!data || data.length===0){
                // generate fake history so chart shows something
                const now = Date.now();
                data = [];
                for(let i=5;i>=1;i--){
                    data.push({
                        recorded_at: new Date(now - i*86400000).toISOString(),
                        accuracy: 0.6 + Math.random()*0.3,
                        avg_response_time: 15 + Math.random()*10
                    });
                }
            }
            drawHistoryChart(data);
        })
        .catch(err=>console.error('history error', err));
}

function drawHistoryChart(records){
    const ctx=document.getElementById('historyChart').getContext('2d');
    const times = records.map(r=> new Date(r.recorded_at).toLocaleDateString());
    const accuracies = records.map(r=> r.accuracy*100);
    const responses = records.map(r=> r.avg_response_time);
    new Chart(ctx,{
        type:'line',
        data:{
            labels:times,
            datasets:[
                {label:'Accuracy (%)',data:accuracies,borderColor:'#0d47a1',fill:false},
                {label:'Avg Response',data:responses,borderColor:'#c62828',fill:false}
            ]
        },
        options:{responsive:true,maintainAspectRatio:false}
    });
}

function fetchMarks(){
    fetch('/marks')
        .then(r=>r.json())
        .then(data=>{
            console.log('marks data', data);
            drawHistogram(data);
        })
        .catch(err=>console.error('marks error', err));
}

function drawHistogram(values){
    if(!values || !values.length) return;
    const bins = Array(10).fill(0);
    const maxMark = 100;
    values.forEach(v=>{
        let idx = Math.floor(v/10);
        if(idx<0) idx=0;
        if(idx>=bins.length) idx=bins.length-1;
        bins[idx]++;
    });
    const labels = bins.map((_,i)=>`${i*10}-${(i+1)*10-1}`);
    const ctx=document.getElementById('marksHistogram').getContext('2d');
    new Chart(ctx,{
        type:'bar',
        data:{
            labels:labels,
            datasets:[
                {
                    label:'Students',
                    data:bins,
                    backgroundColor:'#ff9800',
                    borderColor:'#e65100',
                    borderWidth:2
                }
            ]
        },
        options:{
            responsive:true,
            maintainAspectRatio:false,
            scales:{y:{beginAtZero:true,title:{display:true,text:'Count'}}},
            plugins:{title:{display:true,text:'Marks Distribution (0-100)'}}
        }
    });
}
async function askAI(conversation) {
  console.log('askAI request', conversation);
  try {
    const res = await fetch("/ask-ai", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({conversation})
    });
    if(!res.ok) {
      console.error('AI request failed', res.status, res.statusText);
      return 'Error: could not reach AI server (' + res.status + ')';
    }
    const data = await res.json();
    console.log('askAI response', data);
    return data.reply || 'No reply returned';
  } catch(err) {
    console.error('askAI error', err);
    return 'Error contacting AI: ' + err.message;
  }
}

let conversation = [];

async function sendAI(){
    const inputEl = document.getElementById("msg");
    const message = inputEl.value.trim();
    if(!message) return;

    appendMessage('user', message);
    conversation.push({role:'user', content: message});
    inputEl.value = '';

    const reply = await askAI(conversation);
    conversation.push({role:'assistant', content: reply});
    appendMessage('bot', reply);
    const output = document.getElementById('result');
    if(output){
        output.innerText = reply;
    }
}

function appendMessage(role, text){
    const log = document.getElementById('chatLog');
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

async function fetchAllData(){
    fetch('/all-data')
        .then(r=>r.json())
        .then(data=>{
            console.log('all data', data);
            displayDataTable(data);
        })
        .catch(err=>console.error('all data error', err));
}

function displayDataTable(data){
    const container = document.getElementById('dataTableContainer');
    if(!container) return;
    
    const rows = [];
    const fields = new Set();
    
    if(data.behavior_history && data.behavior_history.length){
        data.behavior_history.forEach(record=>{
            rows.push({
                type:'Behavior',
                studentId: record.student_id,
                accuracy: (record.accuracy*100).toFixed(1),
                responseTime: record.avg_response_time.toFixed(1),
                cluster: record.cluster,
                recommendation: record.recommendation,
                date: new Date(record.recorded_at).toLocaleDateString()
            });
            fields.add('type');
            fields.add('studentId');
            fields.add('accuracy');
            fields.add('responseTime');
            fields.add('cluster');
            fields.add('recommendation');
            fields.add('date');
        });
    }
    
    if(data.logs && data.logs.length){
        data.logs.forEach(log=>{
            rows.push({
                type:'Log',
                studentId: log.student_id,
                responseTime: log.response_time.toFixed(1),
                marks: log.marks,
                date: new Date(log.logged_at).toLocaleDateString()
            });
            fields.add('type');
            fields.add('studentId');
            fields.add('responseTime');
            fields.add('marks');
            fields.add('date');
        });
    }
    
    if(data.marks && data.marks.length){
        data.marks.forEach((mark,idx)=>{
            rows.push({
                type:'Mark',
                marks: mark.marks || mark,
                date: new Date().toLocaleDateString()
            });
            fields.add('type');
            fields.add('marks');
            fields.add('date');
        });
    }
    
    rows.sort((a,b)=>{
        const aId = a.studentId || '';
        const bId = b.studentId || '';
        return String(aId).localeCompare(String(bId));
    });
    
    const fieldOrder = ['type','studentId','accuracy','responseTime','marks','cluster','recommendation','date'];
    const activeFields = fieldOrder.filter(f=>fields.has(f));
    const headers = {
        type:'Type',
        studentId:'Student ID',
        accuracy:'Accuracy(%)',
        responseTime:'Response Time(s)',
        marks:'Marks',
        cluster:'Cluster',
        recommendation:'Recommendation',
        date:'Date'
    };
    
    let html='<table><thead><tr>';
    activeFields.forEach(f=>html+=`<th>${headers[f]}</th>`);
    html+='</tr></thead><tbody>';
    
    rows.forEach(row=>{
        html+='<tr>';
        activeFields.forEach(f=>html+=`<td>${row[f] || '-'}</td>`);
        html+='</tr>';
    });
    html+='</tbody></table>';
    
    container.innerHTML=html;
}

const msgInput = document.getElementById('msg');
if(msgInput){
    msgInput.addEventListener('keydown', function(e){
        if(e.key === 'Enter'){
            e.preventDefault();
            sendAI();
        }
    });
}

// add edge to backend database
function addEdge(){
    const frm = document.getElementById('edgeFrom').value.trim();
    const to = document.getElementById('edgeTo').value.trim();
    const cost = parseFloat(document.getElementById('edgeCost').value);
    if(!frm||!to||isNaN(cost)){
        alert('fill all edge fields');
        return;
    }
    fetch('/add-edge',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({from:frm,to:to,cost:cost})
    }).then(r=>r.json()).then(d=>{
        if(d.status==='ok') alert('edge added');
        else alert('error: '+d.message);
    }).catch(e=>alert('network error'));
}