# 实施计划与接口

根代理：数据库、论文解析/检索、模型接口和 HTTP 集成。
前端代理：frontend/ 界面和浏览器测试。
分析代理：统计引擎、图表和复现包。
交付代理：示例、README、启动脚本。
完成构建、pytest、浏览器闭环和干净环境复现验证。

## HTTP
JSON API 前缀 /api；错误 {detail:string}；ID 字符串；时间 ISO。
- GET/POST /projects -> Project[] / Project；PATCH /projects/{id}。字段 name,question,hypothesis,tags:string[],notes,archived。
- GET /projects/{id}/overview -> {paper_count,pending_jobs,experiment_count,report_count,recent_experiments:[],recent_reports:[]}。
- GET /settings -> {chat_configured,embedding_configured,ai_enabled,chat_model,embedding_model,chat_base_url,embedding_base_url,limits}；PATCH {ai_enabled:bool}。
- GET/POST /projects/{id}/papers：POST multipart files 多文件 -> {papers:Paper[],duplicates:string[]}；GET -> Paper[]。Paper 有 title,authors,year,doi,tags,reading_status,notes,status,error,filename,size_bytes,page_count,created_at。
- GET/PATCH/DELETE /projects/{id}/papers/{paper_id}。GET 额外 pages:[{page_number,text}], jobs:[]。
- GET /projects/{id}/papers/{paper_id}/file -> PDF；POST .../retry -> Job。
- GET /projects/{id}/jobs -> Job[]；Job {id,kind,status,error,resource_id,created_at}。
- POST /projects/{id}/search {query,paper_ids?:[],year?:number,tags?:[],limit?:number} -> {results:Citation[],mode,warnings:[]}。Citation {paper_id,chunk_id,title,page_number,quote,score?}。
- POST /projects/{id}/ask {question,paper_ids?:[],conversation_id?:string} -> {conversation_id,answer,mode,citations:[],warnings:[]}；mode offline/ai/no_evidence。
- GET /projects/{id}/conversations -> conversations 带 messages；message {role,content,citations:[],mode}。
- POST /projects/{id}/papers/{paper_id}/reading-card -> {mode,fields:[{name,text,citations:[]}],warnings:[]}。
- POST /projects/{id}/compare {paper_ids:[]} -> {mode,rows:[{paper_id,title,fields:[{name,text,citations:[]}]}],warnings:[]}。
- POST /projects/{id}/embeddings/rebuild -> Job。
- GET/POST /projects/{id}/experiments -> Experiment[] / Experiment；字段 name,hypothesis,paper_ids:[],conditions,parameters,notes。
- GET /projects/{id}/experiments/{experiment_id} -> Experiment 附 datasets:DatasetVersion[],analyses:AnalysisRun[]。
- POST /projects/{id}/experiments/{experiment_id}/datasets multipart file,sheet可选 -> DatasetVersion。
- POST /projects/{id}/experiments/{experiment_id}/datasets/{dataset_id}/clean {drop_missing_columns?:[],drop_duplicate_rows?:bool} -> 新 DatasetVersion。
- DatasetVersion {id,experiment_id,project_id,filename,sha256,parent_id,sheet,sheets:[],columns:[],row_count,preview:object[],quality:object,transform:object,created_at}。
- GET /projects/{id}/datasets/{dataset_id}/preview?sheet=... -> {sheets,columns,row_count,preview,quality}。
- POST /projects/{id}/experiments/{experiment_id}/analyses {dataset_id,config:AnalysisConfig} -> AnalysisRun {id,result,config,dataset_id,created_at}。
- POST /projects/{id}/experiments/{experiment_id}/suggest {dataset_id,question} -> {configured,suggestion:object,requires_confirmation:true}，不执行。
- GET /projects/{id}/analyses/{analysis_id} -> AnalysisRun；GET .../plot.png?kind=points|box|hist -> PNG。
- GET/POST /projects/{id}/reports -> Report[] / Report。POST {analysis_id,title?}；Report {id,title,analysis_id,markdown,created_at}。
- GET /projects/{id}/reports/{report_id}/download?format=zip|md|csv|png|py|json -> 下载。
- POST /demo -> {project_id}：显式导入示例，无默认假数据。

## 统计接口
app.stats_engine: AnalysisConfig Pydantic；read_dataset(path,sheet=None)->(DataFrame,list[str])；profile_dataframe(df)->dict；analyze(df,config)->dict。
config: group_column,metric_column,group_a,group_b,design(descriptive|independent|paired),experimental_unit,missing_policy(error|drop),alternative(two-sided|less|greater),pair_column?,sample_id_column?,unit,direction(higher|lower),confirmed(bool)。
result JSON安全：summary:[{group,n,mean,median,std,min,max}], comparison:{difference,relative_change_percent,ci_low,ci_high,pvalue,statistic,df,method,status,reason}, points:[{group,value,pair_id?}], warnings:[], exclusions:[], config。
差值 B-A；单侧检验方向同 B-A；relative_change_percent=(B-A)/abs(A)*100，direction仅解释改善方向。
app.exports: render_plot(result,kind='points')->bytes；build_markdown(context)->str；build_export(context,raw_path)->dict[str,bytes]。
context 包含 project,experiment,dataset,analysis(含config,result),citations,report_title,versions。
输出含 original/<原始扩展名>, report.md, summary.csv, plot.png, box.png, histogram.png, reproduce.py, analysis_config.json, provenance.json, requirements.txt。脚本可复制 stats_engine.py放包，不能依赖本项目环境。


数据库会话以 FastAPI function scope 结束，确保提交发生在响应发送前，避免浏览器保存后立即刷新读到旧列表。参考：https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope
