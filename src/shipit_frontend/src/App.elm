port module App exposing (..)

import Dict exposing ( Dict )
import Html exposing ( Html, div, nav, button, text, a, ul, li, footer, hr, span, strong, p, h4 )
import Html.App
import Html.Attributes exposing ( attribute, id, class, type', href, target )
import Html.Events as Events
import Http
import Json.Decode as JsonDecode exposing ( (:=) )
import Navigation exposing ( Location )
import RouteUrl exposing ( UrlChange )
import RouteUrl.Builder as Builder exposing ( Builder, builder, replacePath )
import Result exposing ( Result(Ok, Err))
import RemoteData as RemoteData exposing ( RemoteData(Loading, Success, NotAsked, Failure) )
import String

import App.Home as Home 
import App.ReleaseDashboard as ReleaseDashboard
import App.Utils exposing ( eventLink )

import TaskclusterLogin as User
import BugzillaLogin as Bugzilla
import Hawk


-- TODO:
--   - add NotFound page and redirect to it when route not found
--


type Page
    = Home
    | ReleaseDashboard
    | Bugzilla


type alias Model = {
  release_dashboard : ReleaseDashboard.Model,
  current_page : Page,
  current_user : Maybe User.Model,
  backend_dashboard_url: String,
  bugzilla_url: String
}

type Msg
    = ShowPage Page
    | UserMsg User.Msg -- triggers fetch all analysis
    | HawkMsg Hawk.Msg -- update current hawk header
    | ReleaseDashboardMsg ReleaseDashboard.Msg
    | BugzillaMsg Bugzilla.Msg
    | FetchAnalysis ReleaseDashboard.Analysis

type alias Flags = {
  backend_dashboard_url: String,
  bugzilla_url: String
}

pageLink page attributes =
    eventLink (ShowPage page) attributes

analysisLink analysis attributes =
    eventLink (FetchAnalysis analysis) attributes


delta2url' : Model -> Model -> Maybe Builder
delta2url' previous current =
    case current.current_page of
        ReleaseDashboard ->
          let
            path = case current.release_dashboard.current_analysis of
              Success analysis -> [ "release-dashboard", (toString analysis.id) ]
              _ -> [ "release-dashboard" ]
          in
            Maybe.map
                (Builder.prependToPath path)
                (Just builder)
        Bugzilla ->
            Maybe.map
                (Builder.prependToPath ["bugzilla"])
                (Just builder)
        _ ->
            Maybe.map
                (Builder.prependToPath [])
                (Just builder)

delta2url : Model -> Model -> Maybe UrlChange
delta2url previous current =
    Maybe.map Builder.toUrlChange <| delta2url' previous current


location2messages' : Builder -> List Msg
location2messages' builder =
    case Builder.path builder of
        first :: rest ->
            let
                builder' = Builder.replacePath rest builder
            in
                case first of
                    "login" ->
                        [ 
                          Builder.query builder
                              |> User.convertUrlQueryToUser
                              |> User.LoggingIn
                              |> UserMsg
                        , ShowPage Home
                        ]
                    "bugzilla" ->
                        [ 
                          ShowPage Bugzilla
                        ]
                    "release-dashboard" ->
                      let
                        messages = if List.length rest == 1 then
                          case List.head rest of
                            Just analysisId -> 
                              case String.toInt analysisId |> Result.toMaybe of
                                Just analysisId' ->
                                  -- Load specified analysis 
                                  [ ReleaseDashboardMsg (ReleaseDashboard.FetchAnalysis analysisId') ]
                                Nothing -> [] -- not a string
                            Nothing -> [] -- empty string
                        else
                          [] -- No sub query parts
                      in
                        -- Finish by showing the page
                        messages ++ [ShowPage ReleaseDashboard]

                    -- TODO: This should redirect to NotFound
                    _ ->
                        [ ShowPage Home ]
        _ ->
            [ ShowPage Home ]

location2messages : Location -> List Msg
location2messages location =
    location2messages'
        <| Builder.fromUrl location.href


init : Flags -> (Model, Cmd Msg)
init flags =
    let
        (dashboard, newCmd) = ReleaseDashboard.init flags.backend_dashboard_url
        (user, userCmd) = User.init flags.backend_dashboard_url flags.bugzilla_url
    in
    (
      {
         release_dashboard = dashboard,
         current_page = Home,
         current_user = user,
         backend_dashboard_url = flags.backend_dashboard_url,
         bugzilla_url = flags.bugzilla_url
      },
      -- Follow through with sub parts init
      Cmd.batch [
        Cmd.map ReleaseDashboardMsg newCmd,
        Cmd.map UserMsg userCmd
      ]
    )


update : Msg -> Model -> (Model, Cmd Msg)
update msg model =
    case msg of
        ShowPage page ->
            ( { model | current_page = page }, Cmd.none )

        FetchAnalysis analysis ->
            let
                (newModel, newUser, newCmd) = ReleaseDashboard.update (ReleaseDashboard.FetchAnalysis analysis.id) model.release_dashboard model.current_user
            in
                (
                  { model | release_dashboard = newModel, current_page = ReleaseDashboard, current_user = newUser },
                  Cmd.map ReleaseDashboardMsg newCmd
                )

        ReleaseDashboardMsg msg' ->
            let
                (newModel, newUser, newCmd) = ReleaseDashboard.update msg' model.release_dashboard model.current_user
            in
                (
                  { model | release_dashboard = newModel, current_user = newUser },
                  Cmd.map ReleaseDashboardMsg newCmd
                )

        BugzillaMsg msg' ->
            let
                (newUser, userCmd) = Bugzilla.update msg' model.current_user
            in
                (
                  { model | current_user = newUser },
                  Cmd.map UserMsg userCmd
                )

        UserMsg usermsg -> 
          case usermsg of
            User.LoggedIn _ -> 
              let
                -- Update current user
                (newUser, _, userCmd) = User.update usermsg model.current_user

                -- Reload all analysis on an user update
                (newDashboard, newUser', newCmd) = ReleaseDashboard.update ReleaseDashboard.FetchAllAnalysis model.release_dashboard newUser
              in
                (
                  { model | current_user = newUser', release_dashboard = newDashboard },
                  Cmd.batch [
                    Cmd.map UserMsg userCmd,
                    Cmd.map ReleaseDashboardMsg newCmd
                  ]
                )

            _ ->
              let
                -- Just Update current user
                (newUser, _, userCmd) = User.update usermsg model.current_user
              in
                (
                  { model | current_user = newUser },
                  Cmd.map UserMsg userCmd
                )

        HawkMsg usermsg -> 
            let
              -- Update current user
              (newUser, workflows, userCmd) = User.update usermsg model.current_user
            in
              List.foldr mapHawkToMessages ({model | current_user = newUser}, Cmd.map UserMsg userCmd) workflows

mapHawkToMessages : User.Hawk -> (Model, Cmd Msg) -> (Model, Cmd Msg)
mapHawkToMessages workflow full =
  let
    (model, cmd) = full
    -- Send message to sub parts to process requests
    (dashboard, newUser, dashboardCmd) = ReleaseDashboard.update (ReleaseDashboard.ProcessWorkflow workflow) model.release_dashboard model.current_user
    (newUser', _, userCmd) = User.update (User.ProcessWorkflow workflow) newUser
  in
    (
      { model | current_user = newUser', release_dashboard = dashboard },
      Cmd.batch [
        cmd,
        Cmd.map UserMsg userCmd,
        Cmd.map ReleaseDashboardMsg dashboardCmd
      ]
    )
    

viewPage model =
    case model.current_page of
        Home ->
            Home.view model
        Bugzilla ->
            Html.App.map BugzillaMsg (Bugzilla.view model.current_user)
        ReleaseDashboard ->
            Html.App.map ReleaseDashboardMsg (ReleaseDashboard.view model.release_dashboard)


viewDropdown title pages =
    [ div [ class "dropdown" ]
          [ a [ class "nav-link dropdown-toggle btn btn-primary"
              , id ("dropdown" ++ title)
              , href "#"
              , attribute "data-toggle" "dropdown"
              , attribute "aria-haspopup" "true"
              , attribute "aria-expanded" "false"
              ]
              [ text title ]
          , div [ class "dropdown-menu dropdown-menu-right"
                , attribute "aria-labelledby" "dropdownServices"
                ] pages
          ]
    ]

viewLogin =
  let
      loginTarget =
          Just ( "/login"
               , "Uplift dashboard helps Mozilla Release Management team in their workflow."
               )
      loginUrl =
          { url = "https://login.taskcluster.net"
          , target = loginTarget
          , targetName = "target"
          }
      loginMsg = UserMsg <| User.Login loginUrl
  in
      [ eventLink loginMsg [ class "nav-link" ] [ text "Login TaskCluster" ]
      ]

viewLoginBugzilla =
  [ 
    eventLink (ShowPage Bugzilla) [ class "nav-link" ] [ text "Login Bugzilla" ]
  ]

viewUser model =
  case model.current_user.user of
    Just user ->
      viewDropdown user.clientId [
        -- Link to TC manager
        a [ class "dropdown-item",
            href "https://tools.taskcluster.net/credentials",
            target "_blank"
        ] [ text "Manage credentials" ],

        -- Display bugzilla status
        viewBugzillaCreds model.current_user,

        -- Logout from TC
        div [class "dropdown-divider"] [],
        eventLink (UserMsg User.Logout) [ class "dropdown-item" ] [ text "Logout" ]
      ]

    Nothing -> viewLogin


viewNavBar model =
    [ button [ class "navbar-toggler hidden-md-up"
             , type' "button"
             , attribute "data-toggle" "collapse"
             , attribute "data-target" ".navbar-collapse"
             , attribute "aria-controls" "navbar-header"
             ]
             [ text "Menu" ]
    , pageLink Home [ class "navbar-brand" ]
                    [ text "Uplift Dashboard" ]
    , div [ class "user collapse navbar-toggleable-sm navbar-collapse" ]
          [ ul [ class "nav navbar-nav" ]
              (List.concat [
                  (viewNavDashboard model.release_dashboard),
                  [li [ class "nav-item float-xs-right" ] ( viewUser model )]
              ])
          ]
    ]

viewNavDashboard: ReleaseDashboard.Model -> List (Html Msg)
viewNavDashboard dashboard = 

  case dashboard.all_analysis of
    NotAsked -> []

    Loading -> [
      li [class "nav-item text-info"] [text "Loading Bugs analysis..."] 
    ]

    Failure err -> [
      li [class "nav-item text-danger"] [text "No analysis available."]
    ]

    Success allAnalysis -> 
      (List.map viewNavAnalysis allAnalysis)

viewDashboardStatus: ReleaseDashboard.Model -> Html Msg
viewDashboardStatus dashboard = 
  -- Display explicit error messages
  case dashboard.all_analysis of
    Failure err -> 
      div [class "alert alert-danger"] [
        h4 [] [text "Error while loading analysis"],

        case err of
          Http.Timeout ->
            span [] [text "A timeout occured during the request."]

          Http.NetworkError -> 
            span [] [text "A network error occuring during the request, check your internet connectivity."]

          Http.UnexpectedPayload data ->
            let
              l = Debug.log "Unexpected payload: " data
            in
              span [] [text "An unexpected payload was received, check your browser logs"]

          Http.BadResponse code message ->
            case code of
              401 ->
                p [] ([
                  p [] [text "You are not authenticated: please login again."]
                ] ++ viewLogin)

              _ ->
                span [] [text ("The backend produced an error " ++ (toString code) ++ " : " ++ message)]
        ]

    _ -> div [] []

viewNavAnalysis: ReleaseDashboard.Analysis -> Html Msg
viewNavAnalysis analysis =
    li [class "nav-item"] [
      analysisLink analysis [class "nav-link"] [
        span [] [text (analysis.name ++ " ")],
        if analysis.count > 0 then
          span [class "tag tag-pill tag-primary"] [text (toString analysis.count)]
        else
          span [class "tag tag-pill tag-success"] [text (toString analysis.count)]
      ]
    ]

viewBugzillaCreds: User.Model -> Html Msg
viewBugzillaCreds user = 
  case user.bugzilla_check of
    NotAsked ->
      a [class "dropdown-item text-info"] [
        span [] [text "No bugzilla auth"],
        span [] viewLoginBugzilla
      ] 

    Loading ->
      a [class "dropdown-item text-info disabled"] [text "Loading Bugzilla auth."]

    Failure err ->
      a [class "dropdown-item text-danger"] [
        span [] [text ("Error while loading bugzilla auth: " ++ toString err)],
        span []  viewLoginBugzilla
      ]  

    Success valid -> 
      if valid then
        a [class "dropdown-item text-success disabled"] [text "Valid bugzilla auth"]

      else
        a [class "dropdown-item text-danger"] [
          span [] [text "Invalid bugzilla auth"],
          span [] viewLoginBugzilla
        ] 

viewFooter =
  footer [] [
    ul [] [
      li [] [ a [ href "https://github.com/mozilla-releng/services" ] [ text "Github" ]],
      li [] [ a [ href "#" ] [ text "Contribute" ]],
      li [] [ a [ href "#" ] [ text "Contact" ]]
      -- TODO: add version / revision
    ]
  ]

view : Model -> Html Msg
view model =
  div [] [
    nav [ id "navbar", class "navbar navbar-full navbar-dark bg-inverse" ] [
      div [ class "container-fluid" ] ( viewNavBar model )
    ],
    div [ id "content" ] [
      case model.current_user.user of
        Just user ->
          div [class "container-fluid" ] [
            viewDashboardStatus model.release_dashboard,
            viewPage model
          ]
        Nothing ->
          div [class "container"] [
            div [class "alert alert-warning"] [
              text "Please login first."
            ]
          ]
    ],
    viewFooter
  ]


subscriptions : Model -> Sub Msg
subscriptions model =
    Sub.batch [ 
      Sub.map UserMsg (User.localstorage_get (User.LoggedIn)),
      Sub.map HawkMsg (User.hawk_get (User.BuiltHawkHeader)) 
    ]
