import Alpine from 'alpinejs'
function init(){
    return{
      apps: [],
      projects: [],
      images: [],
      selectedProject:null,
      selectedApp:null,
      selectedImg:null,
      error:false,
      error_text:null,
      health_check: false,
      health_status: null,
      image_tag: null,
      health_message: null,
      deploy_loader: false,
      deploy_loader_text: null,
      status_loader: false,
      status_loader_text: null,
      deploy: async function (project,app,image) {
        this.deploy_loader = true
        this.deploy_loader_text = "Submitting Request..."
        let data = { app: app, project: project, image:image }
        let options = {method: 'POST', body: JSON.stringify(data), headers: new Headers({"content-type": "application/json"})}
        await fetch('/deploy', options).then((response) => {
          if (response.ok) {
            this.deploy_loader = false
            this.deploy_loader_text = null
          } else {
            this.deploy_loader = false
            this.deploy_loader_text = null
            this.error = true
            this.error_text = "Deployment request failed"
          }
        }),
        this.status_loader = true
        this.status_loader_text = "Checking Deployment Status..."
        await fetch('/status', options).then((response) => {
          if (response.ok) {
            this.status_loader = false
            this.health_check = true
            this.status_loader_text = null
            response.json().then((response) => {
              for (let i in response){
                if ( i == 'status') {
                  this.health_status = response[i]
                }
                if (i == 'image') {
                  this.image_tag = response[i]
                }
              }
            })
          } else {
            this.status_loader = false
            this.status_loader_text = null
            this.error = true
            this.error_text = "The request failed or unknown response"
          }
        })
      },
      project_list: async function () {
        await fetch('/list_projects').then((response) => {
          if (response.ok) {
            return response.json().then((response) => (this.projects = response))
          } else {
             this.error = true
             this.error_text = "Could not retrieve a list of environments"
          }
        })
      },
      app_list: async function (project) {
        this.images = []
        this.selectedApp = null
        await fetch('/list_apps?project='+project).then((response) => {
          if (response.ok) {
            return response.json().then((response) => (this.apps = response))
          } else {
            this.apps = []
            this.error = true
            this.error_text = "No applications found for the selected environment"
          }
        })
      },
      images_list: async function (app) {
        await fetch('/list_images?app='+app).then((response) => {
          if (response.ok) {
           return response.json().then((response) => (this.images = response))
          } else {
            this.images = []
            this.error = true
            this.error_text = "No images found for the selected application"
          }
        })
      },
    }
  }
window.Alpine = Alpine
Alpine.start()
